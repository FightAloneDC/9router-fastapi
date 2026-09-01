"""Tests for quota usage handlers.

Validates that each provider handler correctly parses
API responses into standardized UsageResponse format.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.quota import (
    get_usage_handler,
    supported_providers,
)
from app.services.quota.base import QuotaItem, UsageResponse
from app.providers.github.quota import GitHubUsageHandler
from app.providers.claude.quota import ClaudeUsageHandler
from app.providers.codex.quota import CodexUsageHandler
from app.providers.kiro.quota import KiroUsageHandler
from app.providers.qoder.quota import (
    QoderUsageHandler,
    credits_from_tokens,
)
from app.providers.groq.quota import (
    GroqUsageHandler,
    lookup_limits,
    merge_live_rows,
    overlay_live_on_published,
    published_quota_rows,
    quotas_from_headers,
    reset_to_iso,
)
from app.providers.openrouter.quota import (
    OpenrouterUsageHandler,
    apply_local_usage,
    lookup_limits as or_lookup_limits,
    quotas_from_headers as or_quotas_from_headers,
)
from app.providers.nvidia.quota import (
    NvidiaUsageHandler,
    apply_local_usage as nv_apply_local_usage,
    lookup_limits as nv_lookup_limits,
    overlay_header_cache as nv_overlay_header_cache,
    quotas_from_headers as nv_quotas_from_headers,
)
from app.providers.cerebras.quota import (
    CerebrasUsageHandler,
    apply_local_usage as cb_apply_local_usage,
    lookup_limits as cb_lookup_limits,
    published_quota_rows as cb_published,
    quotas_from_headers as cb_quotas_from_headers,
)
from app.providers.mistral.quota import (
    MistralUsageHandler,
    apply_local_usage as mi_apply_local_usage,
    lookup_limits as mi_lookup_limits,
    quotas_from_headers as mi_quotas_from_headers,
)
from app.providers.alims_intl.quota import (
    AlimsIntlUsageHandler,
    apply_local_usage as ali_apply_local_usage,
    lookup_limits as ali_lookup_limits,
    published_quota_rows as ali_published,
    quotas_from_headers as ali_quotas_from_headers,
)
from app.providers.cohere.quota import (
    CohereUsageHandler,
    apply_local_usage as co_apply_local_usage,
    lookup_limits as co_lookup_limits,
    quotas_from_headers as co_quotas_from_headers,
    summary_quota_rows as co_summary_quota_rows,
)
from app.providers.voyage_ai.quota import (
    VoyageAiUsageHandler,
    free_token_bars as voyage_free_token_bars,
    lookup_free_tokens as voyage_lookup_free_tokens,
    lookup_limits as voyage_lookup_limits,
    model_detail_rows as voyage_model_detail_rows,
    summary_quota_rows as voyage_summary_quota_rows,
    tier1_minute_bars as voyage_tier1_minute_bars,
)
from app.providers.jina_ai.quota import (
    JinaAiUsageHandler,
    lookup_limits as jina_lookup_limits,
    resolve_plan as jina_resolve_plan,
    summary_quota_rows as jina_summary_quota_rows,
)
from app.providers.grok_cli.quota import (
    DEAD,
    EXHAUSTED,
    GROK_CLI_FREE_DAILY_TOKENS,
    HEALTHY,
    RATE_LIMITED,
    GrokCliUsageHandler,
    _parse_exhausted_tokens,
    _plan_from_access_token,
    classify_health,
)
from app.providers.morph.config import MorphConfig
from app.providers.morph.quota import (
    MorphUsageHandler,
    count_requests_since as morph_count_requests_since,
    monthly_bar as morph_monthly_bar,
)
from app.providers.deepseek.config import DeepseekConfig
from app.providers.deepseek.quota import (
    DeepseekUsageHandler,
    balance_quota_rows,
    lookup_concurrency,
    resolve_plan,
    signup_token_grant,
)


# ──────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────


def test_supported_providers():
    providers = supported_providers()
    assert "github" in providers
    assert "claude" in providers
    assert "codex" in providers
    assert "kiro" in providers
    assert "qoder" in providers
    assert "grok-cli" in providers
    assert "groq" in providers
    assert "openrouter" in providers
    assert "nvidia" in providers
    assert "cerebras" in providers
    assert "mistral" in providers
    assert "alims-intl" in providers
    assert "cohere" in providers
    assert "voyage-ai" in providers
    assert "morph" in providers
    assert "deepseek" in providers


def test_voyage_lookup_limits() -> None:
    """Voyage card uses free-tier maxima; modal is per-model."""
    from datetime import datetime, timezone

    from app.providers.voyage_ai.quota import _default_card_caps

    assert voyage_lookup_limits("voyage-4-lite") == {
        "rpm": 2000,
        "tpm": 16_000_000,
    }
    assert voyage_lookup_limits("voyage/voyage-4-large") == {
        "rpm": 2000,
        "tpm": 3_000_000,
    }
    assert voyage_lookup_limits("rerank-2.5") == {
        "rpm": 2000,
        "tpm": 2_000_000,
    }
    assert voyage_lookup_limits("voyage-3") == {}
    assert voyage_lookup_free_tokens("voyage-4-large") == 200_000_000
    assert voyage_lookup_free_tokens("voyage-4") == 200_000_000
    assert voyage_lookup_free_tokens("voyage-finance-2") == 50_000_000
    assert voyage_lookup_free_tokens("voyage-3.5") is None
    assert "fetch_model_details" in VoyageAiUsageHandler.__dict__

    caps = _default_card_caps()
    assert caps["rpm"] == 2000
    assert caps["tpm"] == 16_000_000
    assert caps["free_tokens"] == 200_000_000

    summary = voyage_summary_quota_rows(
        {"voyage-4-lite": {"requests": 5, "tokens": 100}},
        lifetime_tokens=1_500,
        reset_at="2026-08-25T00:01:00+00:00",
    )
    by_name = {row["name"]: row for row in summary}
    assert set(by_name) == {"free tokens", "RPM", "TPM"}
    assert by_name["free tokens"]["used"] == 1_500
    assert by_name["free tokens"]["total"] == 200_000_000
    assert by_name["free tokens"]["unlimited"] is False
    assert by_name["RPM"]["used"] == 5
    assert by_name["RPM"]["total"] == 2000
    assert by_name["TPM"]["used"] == 100
    assert by_name["TPM"]["total"] == 16_000_000
    assert all(not row["unlimited"] for row in summary)

    grants = voyage_free_token_bars({"voyage-4-large": 1_000})
    grant = next(
        row for row in grants
        if row["name"] == "voyage-4-large free tokens"
    )
    assert grant["total"] == 200_000_000
    assert grant["used"] == 1_000
    grant_names = {row["name"] for row in grants}
    assert "voyage-3.5 free tokens" not in grant_names

    now = datetime(2026, 8, 25, tzinfo=timezone.utc)
    rows = voyage_tier1_minute_bars(
        {"voyage-4-lite": {"requests": 5, "tokens": 100}},
        now,
    )
    names = {row["name"] for row in rows}
    assert "voyage-3 RPM" not in names
    assert "requests (last 60s)" not in names
    rpm = next(row for row in rows if row["name"] == "voyage-4-lite RPM")
    tpm = next(row for row in rows if row["name"] == "voyage-4-lite TPM")
    assert rpm["used"] == 5
    assert rpm["total"] == 2000
    assert tpm["used"] == 100
    assert tpm["total"] == 16_000_000

    grouped = voyage_model_detail_rows(
        {"voyage-4-large": 1_000},
        {"voyage-4-large": {"requests": 2, "tokens": 50}},
        now,
    )
    grouped_names = [row["name"] for row in grouped]
    start = grouped_names.index("voyage-4-large free tokens")
    assert grouped_names[start:start + 3] == [
        "voyage-4-large free tokens",
        "voyage-4-large RPM",
        "voyage-4-large TPM",
    ]
    assert "voyage-3.5 free tokens" not in grouped_names


def test_jina_quota_endpoint_caps_and_free_tokens() -> None:
    """Jina: endpoint RPM/TPM + operator free tokens from RATE_LIMITS."""
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.quota import free_token_grant

    cfg = JinaAiConfig()
    assert "FREE_TOKENS" not in JinaAiConfig.model_fields
    assert free_token_grant() == cfg.RATE_LIMITS["free"]["tokens"]
    assert free_token_grant() == 10_000_000

    assert jina_resolve_plan(None) == "free"
    assert jina_resolve_plan({"accountType": "premium"}) == "premium"
    assert jina_resolve_plan({"accountType": "payg"}) == "premium"
    assert jina_resolve_plan({"accountType": "subscribe"}) == "premium"
    assert jina_resolve_plan({"accountType": "paid"}) == "free"
    assert jina_lookup_limits("free") == {
        "rpm": 500,
        "tpm": 1_000_000,
    }
    assert jina_lookup_limits("premium") == {
        "rpm": 2000,
        "tpm": 5_000_000,
    }
    assert JinaAiUsageHandler.USES_UPSTREAM is False
    assert "fetch_model_details" not in JinaAiUsageHandler.__dict__

    rows = jina_summary_quota_rows(
        lifetime_tokens=12_000,
        minute_requests=3,
        minute_tokens=400,
        plan="free",
        reset_at="2026-08-25T00:01:00+00:00",
    )
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"free tokens", "RPM", "TPM"}
    assert by_name["free tokens"]["total"] == free_token_grant()
    assert by_name["free tokens"]["used"] == 12_000
    assert by_name["RPM"]["total"] == 500
    assert by_name["RPM"]["used"] == 3
    assert by_name["TPM"]["total"] == 1_000_000
    assert by_name["TPM"]["used"] == 400

    premium = jina_summary_quota_rows(
        lifetime_tokens=0,
        minute_requests=0,
        minute_tokens=0,
        plan="premium",
        reset_at=None,
    )
    prem = {row["name"]: row for row in premium}
    assert set(prem) == {"RPM", "TPM"}
    assert prem["RPM"]["total"] == 2000
    assert prem["TPM"]["total"] == 5_000_000


def test_get_handler_known():
    handler = get_usage_handler("github")
    assert handler is not None
    assert isinstance(handler, GitHubUsageHandler)


def test_get_handler_unknown():
    handler = get_usage_handler("nonexistent")
    assert handler is None


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _mock_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    return resp


# ──────────────────────────────────────────────
# GitHub
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_github_paid_plan():
    handler = GitHubUsageHandler()
    mock_resp = _mock_response(200, {
        "copilot_plan": "individual",
        "quota_snapshots": {
            "chat": {
                "entitlement": 1500,
                "remaining": 1200,
                "unlimited": False,
            },
            "completions": {
                "entitlement": 3000,
                "remaining": 2800,
                "unlimited": False,
            },
        },
        "quota_reset_date": "2026-08-01T00:00:00Z",
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert isinstance(result, UsageResponse)
    assert result.plan == "Individual"
    assert len(result.quotas) == 2

    chat = next(q for q in result.quotas if q.name == "Chat")
    assert chat.used == 300
    assert chat.total == 1500
    assert chat.remaining == 1200
    assert chat.remaining_percentage == 80.0
    assert chat.reset_at == "2026-08-01T00:00:00Z"


@pytest.mark.asyncio
async def test_github_free_plan():
    handler = GitHubUsageHandler()
    mock_resp = _mock_response(200, {
        "copilot_plan": "free",
        "monthly_quotas": {"chat": 50, "completions": 2000},
        "limited_user_quotas": {"chat": 10, "completions": 500},
        "limited_user_reset_date": "2026-08-01T00:00:00Z",
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert result.plan == "Free"
    assert len(result.quotas) == 2
    # limited_user_quotas takes priority
    chat = next(q for q in result.quotas if q.name == "Chat")
    assert chat.total == 10


@pytest.mark.asyncio
async def test_github_api_error():
    handler = GitHubUsageHandler()
    mock_resp = _mock_response(401, {})

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("bad-token")

    assert "401" in result.message
    assert len(result.quotas) == 0


# ──────────────────────────────────────────────
# Claude
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claude_usage():
    handler = ClaudeUsageHandler()
    mock_resp = _mock_response(200, {
        "five_hour": {
            "utilization": 45,
            "resets_at": 1719500000,
        },
        "seven_day": {
            "utilization": 23,
            "resets_at": 1719900000,
        },
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert result.plan == "Pro"
    assert len(result.quotas) == 2

    session = next(
        q for q in result.quotas
        if q.name == "Session (5h)"
    )
    assert session.used == 45
    assert session.total == 100
    assert session.remaining_percentage == 55.0
    assert not result.limit_reached


@pytest.mark.asyncio
async def test_claude_rate_limited():
    handler = ClaudeUsageHandler()
    mock_resp = _mock_response(429, {})

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert "Rate limited" in result.message


@pytest.mark.asyncio
async def test_claude_limit_reached():
    handler = ClaudeUsageHandler()
    mock_resp = _mock_response(200, {
        "five_hour": {"utilization": 100},
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert result.limit_reached
    assert result.quotas[0].remaining_percentage == 0.0


# ──────────────────────────────────────────────
# Codex
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_codex_usage():
    handler = CodexUsageHandler()
    mock_resp = _mock_response(200, {
        "plan_type": "pro",
        "rate_limit": {
            "primary_window": {
                "used_percent": 35,
                "reset_at": "2026-07-27T00:00:00Z",
            },
            "secondary_window": {
                "used_percent": 12,
                "reset_at": "2026-08-01T00:00:00Z",
            },
        },
        "rate_limit_reset_credits": {
            "available_count": 2,
        },
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert result.plan == "Pro"
    assert len(result.quotas) == 3

    session = next(
        q for q in result.quotas if q.name == "Session"
    )
    assert session.used == 35
    assert session.remaining_percentage == 65.0

    credits = next(
        q for q in result.quotas
        if q.name == "Reset Credits"
    )
    assert credits.remaining == 2


# ──────────────────────────────────────────────
# Kiro
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kiro_usage():
    handler = KiroUsageHandler()
    mock_resp = _mock_response(200, {
        "subscriptionInfo": {
            "subscriptionTitle": "Kiro Pro",
        },
        "usageBreakdownList": [
            {
                "resourceType": "AGENTIC_REQUEST",
                "currentUsageWithPrecision": 150,
                "usageLimitWithPrecision": 1000,
                "nextDateReset": "2026-08-01T00:00:00Z",
            },
        ],
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert result.plan == "Kiro Pro"
    assert len(result.quotas) == 1

    q = result.quotas[0]
    assert q.name == "Agentic Request"
    assert q.used == 150
    assert q.total == 1000
    assert q.remaining == 850
    assert q.remaining_percentage == 85.0


# ──────────────────────────────────────────────
# Qoder
# ──────────────────────────────────────────────


def test_qoder_config_limits_no_invented_rpm() -> None:
    from app.providers.qoder.config import QoderConfig

    limits = QoderConfig().RATE_LIMITS
    assert limits == {"trial": {"credits": 300, "days": 14}}
    assert "rpm" not in limits["trial"]
    assert "tpm" not in limits["trial"]


def test_grok_cli_config_limits_two_tiers() -> None:
    from app.providers.grok_cli.config import GrokCliConfig

    limits = GrokCliConfig().RATE_LIMITS
    assert limits == {
        "free/1m": {"tpd": 1_000_000, "requests": 21},
        "free/500k": {"tpd": 500_000, "requests": 21},
    }
    assert "rpm" not in limits["free/1m"]
    assert "tpm" not in limits["free/500k"]


@pytest.mark.asyncio
async def test_qoder_usage():
    handler = QoderUsageHandler()
    # Real Qoder response shape (verified 2026-08)
    mock_resp = _mock_response(200, {
        "userType": "personal_professional_trial",
        "usageType": "credits",
        "isQuotaExceeded": False,
        "expiresAt": 1787423063188,
        "userQuota": {
            "total": 300.0,
            "used": 43.0,
            "remaining": 257.0,
            "percentage": 85.67,
            "unit": "credits",
        },
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert QoderUsageHandler.USES_UPSTREAM is False
    assert result.plan == "personal_professional_trial"
    assert result.limit_reached is False
    assert len(result.quotas) == 1

    credits = result.quotas[0]
    assert credits.name == "Credits"
    assert credits.used == 43
    assert credits.total == 300
    assert credits.remaining == 257
    assert abs(credits.remaining_percentage - 85.67) < 0.01
    assert credits.reset_at is not None


@pytest.mark.asyncio
async def test_qoder_usage_farm_trial_end_when_api_omits_expires():
    handler = QoderUsageHandler()
    mock_resp = _mock_response(200, {
        "userType": "personal_professional_trial",
        "usageType": "credits",
        "isQuotaExceeded": False,
        "userQuota": {
            "total": 300.0,
            "used": 43.0,
            "remaining": 257.0,
            "unit": "credits",
        },
    })
    trial_end = "2026-09-01T10:59:32.131000+00:00"
    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch(
            "fake-token",
            {
                "expiresAt": "2026-08-28T14:24:01+00:00",
                "proTrialEndAt": trial_end,
                "farmQuotaRemaining": 300,
            },
        )
    credits = result.quotas[0]
    assert credits.remaining == 257
    assert credits.reset_at == trial_end


@pytest.mark.asyncio
async def test_qoder_usage_falls_back_to_farm_snapshot():
    handler = QoderUsageHandler()
    trial_end = "2026-09-01T10:59:32.131000+00:00"
    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        side_effect=RuntimeError("down"),
    ):
        result = await handler.fetch(
            "fake-token",
            {
                "proTrialEndAt": trial_end,
                "farmQuotaTotal": 300,
                "farmQuotaRemaining": 180,
                "farmQuotaExceeded": False,
                "userType": "personal_professional_trial",
            },
        )
    assert result.plan == "personal_professional_trial"
    credits = result.quotas[0]
    assert credits.used == 120
    assert credits.remaining == 180
    assert credits.reset_at == trial_end


@pytest.mark.asyncio
async def test_qoder_usage_ignores_job_token_expiry_as_trial():
    handler = QoderUsageHandler()
    mock_resp = _mock_response(200, {
        "userType": "personal_professional_trial",
        "isQuotaExceeded": False,
        "userQuota": {
            "total": 300.0,
            "used": 10.0,
            "remaining": 290.0,
            "unit": "credits",
        },
    })
    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch(
            "fake-token",
            {"expiresAt": "2026-08-28T14:24:01+00:00"},
        )
    assert result.quotas[0].reset_at is None


def test_qoder_credits_from_chat_usage_chunk() -> None:
    """Live SSE usage (verified 2026-09-01) carries credits."""
    assert credits_from_tokens({
        "billable": True,
        "credits": 1.21,
        "original_credits": 1.21,
        "prompt_tokens": 9,
        "completion_tokens": 11,
    }) == pytest.approx(1.21)
    assert credits_from_tokens(
        json.dumps({"credits": 2.8877612500000005})
    ) == pytest.approx(2.8877612500000005)
    assert credits_from_tokens({"original_credits": 4.5}) == 4.5
    assert credits_from_tokens({}) == 0.0
    assert credits_from_tokens(None) == 0.0


@pytest.mark.asyncio
async def test_qoder_fetch_uses_chat_credits_when_higher():
    handler = QoderUsageHandler()
    mock_resp = _mock_response(200, {
        "userType": "personal_professional_trial",
        "isQuotaExceeded": False,
        "userQuota": {
            "total": 300.0,
            "used": 1.0,
            "remaining": 299.0,
            "unit": "credits",
        },
    })
    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        with patch(
            "app.providers.qoder.quota.local_credits",
            new_callable=AsyncMock,
            return_value=5.9,
        ):
            result = await handler.fetch(
                "fake-token",
                connection_id="fd55d07d-c8f5-401b-9216-59d75060f4a8",
            )
    credits = result.quotas[0]
    assert credits.used == 5
    assert credits.remaining == 295


@pytest.mark.asyncio
async def test_qoder_observe_complete_writes_quota_cache():
    """After a proxied chat, usage_history.tokens.credits
    update quota_cache — same lifecycle as NVIDIA logs.
    """
    handler = QoderUsageHandler()
    conn_id = "fd55d07d-c8f5-401b-9216-59d75060f4a8"
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.commit = AsyncMock()

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
    ) as get_mock:
        with patch(
            "app.providers.qoder.quota.local_credits",
            new_callable=AsyncMock,
            return_value=2.8877612500000005,
        ):
            await handler.observe_complete(db, conn_id)

    get_mock.assert_not_called()
    db.add.assert_called_once()
    db.commit.assert_awaited()
    added = db.add.call_args[0][0]
    rows = json.loads(added.quotas)
    assert rows[0]["used"] == 2
    assert rows[0]["remaining"] == 298
    assert added.limit_reached is False


@pytest.mark.asyncio
async def test_qoder_observe_complete_skips_without_local_credits():
    handler = QoderUsageHandler()
    db = MagicMock()
    db.add = MagicMock()
    with patch.object(
        handler, "_get", new_callable=AsyncMock,
    ) as get_mock:
        with patch(
            "app.providers.qoder.quota.local_credits",
            new_callable=AsyncMock,
            return_value=0.0,
        ):
            await handler.observe_complete(
                db, "fd55d07d-c8f5-401b-9216-59d75060f4a8",
            )
    get_mock.assert_not_called()
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_observe_after_request_skips_default_complete():
    from app.services.quota import observe_after_request

    with patch(
        "app.database.async_session",
    ) as sess:
        await observe_after_request(
            "groq",
            "fd55d07d-c8f5-401b-9216-59d75060f4a8",
        )
    sess.assert_not_called()


@pytest.mark.asyncio
async def test_observe_after_request_dispatches_qoder():
    from app.services.quota import observe_after_request

    db = AsyncMock()
    sess_cm = AsyncMock()
    sess_cm.__aenter__.return_value = db
    with patch(
        "app.database.async_session",
        return_value=sess_cm,
    ):
        with patch.object(
            QoderUsageHandler,
            "observe_complete",
            new_callable=AsyncMock,
        ) as complete:
            await observe_after_request(
                "qoder",
                "fd55d07d-c8f5-401b-9216-59d75060f4a8",
            )
    complete.assert_awaited_once()
    assert complete.call_args.args[1] == (
        "fd55d07d-c8f5-401b-9216-59d75060f4a8"
    )


# ──────────────────────────────────────────────
# Network failure
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_network_error_handled():
    handler = GitHubUsageHandler()

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        side_effect=Exception("Connection refused"),
    ):
        result = await handler.fetch("fake-token")

    assert "Failed to fetch" in result.message
    assert len(result.quotas) == 0


# ──────────────────────────────────────────────
# Base helpers
# ──────────────────────────────────────────────


def test_pct_calculation():
    assert GitHubUsageHandler._pct(0, 100) == 100.0
    assert GitHubUsageHandler._pct(50, 100) == 50.0
    assert GitHubUsageHandler._pct(100, 100) == 0.0
    assert GitHubUsageHandler._pct(0, 0) == 100.0
    assert GitHubUsageHandler._pct(150, 100) == 0.0


# ──────────────────────────────────────────────
# Grok CLI
# ──────────────────────────────────────────────


def _jwt_with_tier(tier: int) -> str:
    """Header.payload.signature stub with a tier claim."""
    import base64, json

    payload = base64.urlsafe_b64encode(
        json.dumps({"tier": tier}).encode()
    ).decode().rstrip("=")
    header = base64.urlsafe_b64encode(
        b'{"alg":"ES256"}'
    ).decode().rstrip("=")
    return f"{header}.{payload}.sig"


def test_grok_plan_from_jwt():
    assert _plan_from_access_token(
        _jwt_with_tier(1)
    ) == "SuperGrok"
    assert _plan_from_access_token(
        _jwt_with_tier(0)
    ) == "Free"
    assert _plan_from_access_token("not-a-jwt") == ""


def test_grok_classify_health():
    # Farm resort-contract tiers
    assert classify_health(
        {"errorCode": "429"}
    )[0] == RATE_LIMITED
    assert classify_health(
        {"errorCode": "402"}
    )[0] == EXHAUSTED
    assert classify_health(
        {"errorCode": "403"}
    )[0] == EXHAUSTED
    assert classify_health({
        "lastError": "personal-team-blocked:spending-limit"
    })[0] == EXHAUSTED
    assert classify_health(
        {"errorCode": "401"}
    )[0] == DEAD
    assert classify_health(
        {"lastError": "invalid_grant"}
    )[0] == DEAD
    assert classify_health(
        {"errorCode": "503"}
    )[0] != EXHAUSTED
    assert classify_health({})[0] == HEALTHY


@pytest.mark.asyncio
async def test_grok_fetch_healthy():
    handler = GrokCliUsageHandler()
    result = await handler.fetch("", {})
    assert result.limit_reached is False
    assert result.message is None
    assert len(result.quotas) == 1
    q = result.quotas[0]
    assert q.total == GROK_CLI_FREE_DAILY_TOKENS
    assert q.used == 0
    assert q.remaining_percentage == 100.0
    assert q.reset_at is not None


@pytest.mark.asyncio
async def test_grok_fetch_exhausted():
    handler = GrokCliUsageHandler()
    result = await handler.fetch("", {
        "errorCode": "402",
        "lastError": "spending-limit",
    })
    assert result.limit_reached is True
    assert result.message
    q = result.quotas[0]
    assert q.used == GROK_CLI_FREE_DAILY_TOKENS
    assert q.remaining_percentage == 0.0


def test_grok_parse_exhausted_tokens():
    actual, limit = _parse_exhausted_tokens(
        "You've used all the included free usage for model "
        "grok-4.5 for now. Usage resets over a rolling 24-hour "
        "window — tokens (actual/limit): 539793/500000. "
        "Upgrade to a Grok subscription for higher limits"
    )
    assert (actual, limit) == (539793, 500000)
    assert _parse_exhausted_tokens("other error") == (None, None)
    assert _parse_exhausted_tokens("") == (None, None)


@pytest.mark.asyncio
async def test_grok_fetch_429_calibration():
    """A recorded free-usage 429 calibrates used/limit from the
    authoritative grok error body (account-specific limits)."""
    handler = GrokCliUsageHandler()
    result = await handler.fetch("", {
        "errorCode": "429",
        "lastError": (
            '{"code":"subscription:free-usage-exhausted",'
            '"error":"... tokens (actual/limit): '
            '539793/500000 ..."}'
        ),
    })
    assert result.limit_reached is True
    q = result.quotas[0]
    assert q.total == 500000
    assert q.used == 500000  # display clamped to total
    assert q.remaining_percentage == 0.0


@pytest.mark.asyncio
async def test_grok_fetch_local_accumulation(monkeypatch):
    """Used = local usage_history sum; limit from header
    snapshot; the requests row passes through."""
    handler = GrokCliUsageHandler()

    async def fake_usage(self, connection_id):
        return 123456

    async def fake_snapshot(self, connection_id):
        return ([
            {
                "name": "Daily free (grok-4.5)",
                "used": 0, "total": 1000000,
                "remaining": 1000000,
                "remaining_percentage": 100.0,
                "reset_at": "2026-08-10T00:00:00+00:00",
                "unlimited": False,
            },
            {
                "name": "Requests",
                "used": 3, "total": 21, "remaining": 18,
                "remaining_percentage": 85.7,
                "reset_at": "2026-08-10T00:00:00+00:00",
                "unlimited": False,
            },
        ], False)

    monkeypatch.setattr(
        GrokCliUsageHandler, "_today_token_usage", fake_usage,
    )
    monkeypatch.setattr(
        GrokCliUsageHandler, "_today_snapshot", fake_snapshot,
    )

    result = await handler.fetch(
        "", {},
        connection_id="9ade4089-4a58-4bae-81de-4654f29b0c5b",
    )
    assert result.limit_reached is False
    assert len(result.quotas) == 2
    token_q = result.quotas[0]
    assert token_q.used == 123456
    assert token_q.total == 1000000
    assert result.quotas[1].name == "Requests"
    assert result.quotas[1].used == 3


def test_groq_handler_registered() -> None:
    handler = get_usage_handler("groq")
    assert handler is not None
    assert isinstance(handler, GroqUsageHandler)


def test_groq_config_limits() -> None:
    caps = lookup_limits("gq/llama-3.1-8b-instant")
    assert caps["rpm"] == 30
    assert caps["rpd"] == 14400
    assert caps["tpm"] == 6000
    compound = lookup_limits("groq/compound")
    assert compound["rpd"] == 250
    assert lookup_limits("unknown-model") == {}


def test_groq_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-requests": "14400",
        "x-ratelimit-remaining-requests": "14370",
        "x-ratelimit-reset-requests": "2m59.56s",
        "x-ratelimit-limit-tokens": "6000",
        "x-ratelimit-remaining-tokens": "5997",
        "x-ratelimit-reset-tokens": "7.66s",
    }
    rows = quotas_from_headers(headers, "llama-3.1-8b-instant")
    names = {r["name"] for r in rows}
    assert any("RPM" in n for n in names)
    assert any("TPD" in n for n in names)
    rpd = next(r for r in rows if "RPD" in r["name"])
    assert rpd["total"] == 14400
    assert rpd["remaining"] == 14370
    assert rpd["used"] == 30
    tpm = next(r for r in rows if "TPM" in r["name"])
    assert tpm["total"] == 6000
    assert tpm["remaining"] == 5997
    assert rpd["reset_at"] is not None
    assert "T" in rpd["reset_at"]


def test_groq_headers_missing_use_config() -> None:
    rows = quotas_from_headers({}, "llama-3.1-8b-instant")
    names = {r["name"] for r in rows}
    assert any("RPD" in n for n in names)
    assert any("TPM" in n for n in names)
    rpd = next(r for r in rows if "RPD" in r["name"])
    assert rpd["total"] == 14400
    assert rpd["remaining"] == 14400


def test_groq_published_rows() -> None:
    rows = published_quota_rows()
    assert rows
    names = {r["name"] for r in rows}
    assert any("llama-3.1-8b-instant" in n for n in names)
    rpd = next(
        r for r in rows if "llama-3.1-8b-instant" in r["name"]
    )
    assert rpd["total"] == 14400
    assert rpd["remaining"] == 14400


def test_groq_reset_duration_to_iso() -> None:
    iso = reset_to_iso("7.66s")
    assert iso is not None
    assert iso.endswith("+00:00") or "T" in iso
    assert reset_to_iso("2m59.56s") is not None


def test_groq_merge_keeps_catalog() -> None:
    live = quotas_from_headers(
        {
            "x-ratelimit-limit-requests": "1000",
            "x-ratelimit-remaining-requests": "991",
            "x-ratelimit-limit-tokens": "8000",
            "x-ratelimit-remaining-tokens": "4300",
        },
        "openai/gpt-oss-120b",
    )
    merged = merge_live_rows(
        published_quota_rows(), live, "openai/gpt-oss-120b",
    )
    names = [r["name"] for r in merged]
    assert any("llama-3.1-8b-instant" in n for n in names)
    rpd = next(
        r for r in merged
        if r["name"] == "openai/gpt-oss-120b requests (RPD)"
    )
    assert rpd["used"] == 9
    healed = overlay_live_on_published(live)
    assert len(healed) > len(live)


def test_openrouter_handler_registered() -> None:
    handler = get_usage_handler("openrouter")
    assert handler is not None
    assert isinstance(handler, OpenrouterUsageHandler)


def test_openrouter_config_limits() -> None:
    free = or_lookup_limits(
        "meta-llama/llama-3.3-70b-instruct:free",
        "free",
    )
    assert free["rpm"] == 20
    assert free["rpd"] == 50
    payg = or_lookup_limits(
        "openrouter/google/gemini-2.0-flash:free",
        "payg",
    )
    assert payg["rpd"] == 1000
    assert or_lookup_limits("openai/gpt-4o", "free") == {}


def test_openrouter_quotas_from_headers() -> None:
    headers = {
        "X-RateLimit-Limit": "50",
        "X-RateLimit-Remaining": "12",
        "X-RateLimit-Reset": "1741305600000",
    }
    rows = or_quotas_from_headers(
        headers,
        "google/gemma-3-27b-it:free",
        "free",
    )
    rpd = next(r for r in rows if "RPD" in r["name"])
    assert rpd["total"] == 50
    assert rpd["remaining"] == 12
    assert rpd["used"] == 38


def test_openrouter_headers_missing_use_config() -> None:
    rows = or_quotas_from_headers(
        {}, "mistralai/mistral-small:free", "free",
    )
    names = {r["name"] for r in rows}
    assert any("RPM" in n for n in names)
    assert any("RPD" in n for n in names)
    rpd = next(r for r in rows if "RPD" in r["name"])
    assert rpd["total"] == 50
    assert rpd["remaining"] == 50


def test_openrouter_local_usage() -> None:
    rows = apply_local_usage("free", 3, 7)
    rpm = next(r for r in rows if "RPM" in r["name"])
    rpd = next(r for r in rows if "RPD" in r["name"])
    assert rpm["used"] == 3
    assert rpm["remaining"] == 17
    assert rpd["used"] == 7
    assert rpd["remaining"] == 43


def test_nvidia_handler_registered() -> None:
    handler = get_usage_handler("nvidia")
    assert handler is not None
    assert isinstance(handler, NvidiaUsageHandler)


def test_nvidia_config_limits() -> None:
    caps = nv_lookup_limits("free")
    assert caps["rpm"] == 40
    assert "rpd" not in caps
    assert nv_lookup_limits("unknown")["rpm"] == 40


def test_nvidia_quotas_from_headers() -> None:
    headers = {
        "X-RateLimit-Limit": "40",
        "X-RateLimit-Remaining": "12",
    }
    rows = nv_quotas_from_headers(headers, "free")
    rpm = next(
        r for r in rows
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["total"] == 40
    assert rpm["remaining"] == 12
    assert rpm["used"] == 28


def test_nvidia_headers_missing_use_config() -> None:
    rows = nv_quotas_from_headers({}, "free")
    rpm = next(r for r in rows if "RPM" in r["name"])
    assert rpm["total"] == 40
    assert rpm["remaining"] == 40


def test_nvidia_local_usage() -> None:
    rows = nv_apply_local_usage("free", 9, 3)
    rpm = next(r for r in rows if "RPM" in r["name"])
    today = next(r for r in rows if "today" in r["name"])
    assert rpm["used"] == 9
    assert rpm["remaining"] == 31
    assert today["used"] == 3
    assert today["unlimited"] is True


def test_nvidia_header_row_name_matches_local() -> None:
    hdr = nv_quotas_from_headers(
        {
            "X-RateLimit-Limit": "40",
            "X-RateLimit-Remaining": "12",
        },
        "free",
    )
    local = nv_apply_local_usage("free", 1, 0)
    hdr_names = {r["name"] for r in hdr}
    local_names = {r["name"] for r in local}
    assert "NIM requests (last 60s / RPM)" in hdr_names
    assert "NIM requests (last 60s / RPM)" in local_names


def test_nvidia_overlay_max_used_when_fresh() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 10,
        "total": 40,
        "remaining": 30,
        "reset_at": "cached-reset",
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 10
    assert rpm["total"] == 40
    assert rpm["reset_at"] == "cached-reset"


def test_nvidia_overlay_keeps_higher_local() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 12, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 3,
        "total": 40,
        "remaining": 37,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 12


def test_nvidia_overlay_ignores_stale_cache() -> None:
    now = datetime.now(timezone.utc)
    stale = now - timedelta(seconds=91)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 40,
        "total": 40,
        "remaining": 0,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, stale, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 2
    assert all(
        r["name"] != "NIM requests (header)" for r in out
    )


def test_nvidia_overlay_missing_fetched_at_is_stale() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (last 60s / RPM)",
        "used": 40,
        "total": 40,
        "remaining": 0,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, None, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 2


def test_nvidia_overlay_appends_fresh_header_row() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (header)",
        "used": 5,
        "total": 80,
        "remaining": 75,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    extra = next(
        r for r in out
        if r["name"] == "NIM requests (header)"
    )
    assert extra["used"] == 5
    assert extra["total"] == 80


def test_nvidia_overlay_aliases_legacy_rpm_name() -> None:
    now = datetime.now(timezone.utc)
    local = nv_apply_local_usage("free", 2, 0)
    cached = [{
        "name": "NIM requests (RPM)",
        "used": 9,
        "total": 40,
        "remaining": 31,
        "reset_at": None,
        "unlimited": False,
    }]
    out = nv_overlay_header_cache(
        local, cached, now, now,
    )
    rpm = next(
        r for r in out
        if r["name"] == "NIM requests (last 60s / RPM)"
    )
    assert rpm["used"] == 9
    assert all(
        r["name"] != "NIM requests (RPM)" for r in out
    )


@pytest.mark.anyio
async def test_nvidia_fetch_applies_fresh_overlay() -> None:
    cid = "11111111-1111-1111-1111-111111111111"
    now = datetime.now(timezone.utc)
    cache = MagicMock()
    cache.quotas = json.dumps([{
        "name": "NIM requests (last 60s / RPM)",
        "used": 10,
        "total": 40,
        "remaining": 30,
        "reset_at": None,
        "unlimited": False,
    }])
    cache.fetched_at = now
    db = AsyncMock()
    db.get = AsyncMock(return_value=cache)
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = False

    handler = NvidiaUsageHandler()
    with (
        patch(
            "app.providers.nvidia.quota._count_requests",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "app.database.async_session",
            return_value=session_cm,
        ),
    ):
        result = await handler.fetch(
            "", {"accountType": "free"}, cid,
        )
    rpm = next(
        q for q in result.quotas
        if q.name == "NIM requests (last 60s / RPM)"
    )
    assert rpm.used == 10


def test_cerebras_handler_registered() -> None:
    handler = get_usage_handler("cerebras")
    assert handler is not None
    assert isinstance(handler, CerebrasUsageHandler)


def test_cerebras_config_limits() -> None:
    free = cb_lookup_limits("cb/gpt-oss-120b", "free")
    assert free["rpm"] == 5
    assert free["tpm"] == 30000
    assert free["tpd"] == 1000000
    payg = cb_lookup_limits("gpt-oss-120b", "payg")
    assert payg["rpm"] == 1000
    assert payg["tpm"] == 1000000
    assert "tpd" not in payg
    assert cb_lookup_limits("unknown", "free") == {}


def test_cerebras_published_rows() -> None:
    rows = cb_published("free")
    names = {r["name"] for r in rows}
    assert any("gpt-oss-120b" in n and "TPD" in n for n in names)
    payg = cb_published("developer")
    assert any("RPM" in r["name"] for r in payg)


def test_cerebras_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-tokens": "30000",
        "x-ratelimit-remaining-tokens": "28000",
        "x-ratelimit-reset-tokens": "7.66s",
    }
    rows = cb_quotas_from_headers(
        headers, "gpt-oss-120b", "free",
    )
    tpm = next(r for r in rows if "TPM" in r["name"])
    assert tpm["total"] == 30000
    assert tpm["remaining"] == 28000
    assert tpm["used"] == 2000
    tpd = next(r for r in rows if "TPD" in r["name"])
    assert tpd["total"] == 1000000


def test_cerebras_headers_minute_suffix() -> None:
    headers = {
        "x-ratelimit-limit-tokens-minute": "30000",
        "x-ratelimit-remaining-tokens-minute": "29000",
    }
    rows = cb_quotas_from_headers(
        headers, "gpt-oss-120b", "free",
    )
    tpm = next(r for r in rows if "TPM" in r["name"])
    assert tpm["used"] == 1000
    assert tpm["remaining"] == 29000


def test_cerebras_local_usage() -> None:
    rows = cb_apply_local_usage(
        "free",
        {"gpt-oss-120b": {"tokens": 120, "requests": 2}},
        {"gpt-oss-120b": {"tokens": 40, "requests": 1}},
    )
    tpd = next(
        r for r in rows
        if r["name"].startswith("gpt-oss-120b")
        and "TPD" in r["name"]
    )
    assert tpd["used"] == 120
    assert tpd["total"] == 1000000
    payg = cb_apply_local_usage(
        "payg",
        {},
        {"gpt-oss-120b": {"tokens": 0, "requests": 3}},
    )
    rpm = next(
        r for r in payg
        if r["name"].startswith("gpt-oss-120b")
        and "RPM" in r["name"]
    )
    assert rpm["used"] == 3
    assert rpm["total"] == 1000


def test_mistral_handler_registered() -> None:
    handler = get_usage_handler("mistral")
    assert handler is not None
    assert isinstance(handler, MistralUsageHandler)


def test_mistral_config_limits() -> None:
    assert mi_lookup_limits("free") == {}
    assert mi_lookup_limits("scale") == {}
    assert mi_lookup_limits("payg") == {}


def test_mistral_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-tokens-minute": "500000",
        "x-ratelimit-remaining-tokens-minute": "499000",
    }
    rows = mi_quotas_from_headers(headers)
    tok = next(r for r in rows if "TPM" in r["name"])
    assert tok["total"] == 500000
    assert tok["used"] == 1000
    assert tok["remaining"] == 499000
    assert tok["reset_at"]


def test_mistral_headers_pair_minute_not_mix() -> None:
    """Ignore non-minute token headers (Studio uses *-minute)."""
    rows = mi_quotas_from_headers({
        "x-ratelimit-limit-tokens": "50000",
        "x-ratelimit-remaining-tokens": "0",
    })
    assert rows == []


def test_mistral_headers_live_req_minute() -> None:
    rows = mi_quotas_from_headers({
        "x-ratelimit-limit-tokens-minute": "50000",
        "x-ratelimit-remaining-tokens-minute": "49979",
        "x-ratelimit-limit-req-minute": "50",
        "x-ratelimit-remaining-req-minute": "49",
    })
    by_name = {r["name"]: r for r in rows}
    assert by_name["Mistral TPM (per minute)"]["total"] == 50000
    assert by_name["Mistral TPM (per minute)"]["used"] == 21
    assert by_name["Mistral RPM (per minute)"]["total"] == 50
    assert by_name["Mistral RPM (per minute)"]["used"] == 1
    assert by_name["Mistral TPM (per minute)"]["reset_at"]


def test_mistral_headers_missing() -> None:
    assert mi_quotas_from_headers({}) == []


def test_mistral_local_usage() -> None:
    rows = mi_apply_local_usage(4, 120, 1)
    today_r = next(
        r for r in rows
        if "requests (today)" in r["name"]
    )
    today_t = next(
        r for r in rows
        if "tokens (today)" in r["name"]
    )
    minute = next(
        r for r in rows if "last 60s" in r["name"]
    )
    assert today_r["used"] == 4
    assert today_r["unlimited"] is True
    assert today_t["used"] == 120
    assert minute["used"] == 1


def test_alims_handler_registered() -> None:
    handler = get_usage_handler("alims-intl")
    assert handler is not None
    assert isinstance(handler, AlimsIntlUsageHandler)


def test_alims_config_limits() -> None:
    caps = ali_lookup_limits("alims-intl/qwen3.7-flash")
    assert caps["rpm"] == 15000
    assert caps["tpm"] == 5000000
    assert ali_lookup_limits("qwen3.7-max")["rpm"] == 600
    assert ali_lookup_limits("qwen3.8-max") == {
        "rpm": 15000, "tpm": 2000000,
    }
    assert ali_lookup_limits("text-embedding-v4") == {
        "rpm": 1800, "tpm": 1000000,
    }
    assert ali_lookup_limits("qwen-image") == {"rpm": 120}
    assert ali_lookup_limits("qwen3-tts-flash") == {"rpm": 180}
    assert ali_lookup_limits("qwen3-asr-flash") == {"rpm": 100}
    assert ali_lookup_limits("unknown") == {}


def test_alims_published_rows() -> None:
    rows = ali_published()
    names = {r["name"] for r in rows}
    assert any(
        "qwen3.7-flash" in n and "RPM" in n for n in names
    )
    assert any(
        "qwen3.7-flash" in n and "TPM" in n for n in names
    )
    assert any(
        "text-embedding-v4" in n and "RPM" in n for n in names
    )
    assert any(
        n.startswith("qwen-image ") and "RPM" in n for n in names
    )
    # Image models have no TPM column in the docs.
    assert not any(
        n.startswith("qwen-image ") and "TPM" in n for n in names
    )
    # Full catalog stays for detail modal — but list fetch must
    # not ship it (see test_alims_summary_rows).
    assert len(rows) > 50


def test_alims_summary_rows() -> None:
    from app.providers.alims_intl.quota import summary_quota_rows

    rows = summary_quota_rows({
        "qwen3.7-flash": {"tokens": 400, "requests": 2},
        "qwen-image": {"tokens": 0, "requests": 1},
    })
    assert len(rows) == 2
    by_name = {r["name"]: r for r in rows}
    assert by_name["requests (last 60s)"]["used"] == 3
    assert by_name["requests (last 60s)"]["unlimited"] is True
    assert by_name["tokens (last 60s)"]["used"] == 400
    assert by_name["tokens (last 60s)"]["unlimited"] is True


def test_alims_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-tokens": "5000000",
        "x-ratelimit-remaining-tokens": "4990000",
        "x-ratelimit-limit-requests": "15000",
        "x-ratelimit-remaining-requests": "14990",
    }
    rows = ali_quotas_from_headers(
        headers, "qwen3.7-flash",
    )
    tpm = next(r for r in rows if "TPM" in r["name"])
    rpm = next(r for r in rows if "RPM" in r["name"])
    assert tpm["total"] == 5000000
    assert tpm["used"] == 10000
    assert rpm["total"] == 15000
    assert rpm["used"] == 10


def test_alims_local_usage() -> None:
    rows = ali_apply_local_usage({
        "qwen3.7-flash": {"tokens": 400, "requests": 2},
    })
    rpm = next(
        r for r in rows
        if r["name"].startswith("qwen3.7-flash")
        and "RPM" in r["name"]
    )
    tpm = next(
        r for r in rows
        if r["name"].startswith("qwen3.7-flash")
        and "TPM" in r["name"]
    )
    assert rpm["used"] == 2
    assert rpm["total"] == 15000
    assert tpm["used"] == 400
    assert tpm["total"] == 5000000


def test_cohere_handler_registered() -> None:
    handler = get_usage_handler("cohere")
    assert handler is not None
    assert isinstance(handler, CohereUsageHandler)


def test_cohere_config_limits() -> None:
    assert co_lookup_limits(
        "command-a-03-2025", "free",
    )["rpm"] == 20
    assert co_lookup_limits(
        "co/command-a-03-2025", "payg",
    )["rpm"] == 500
    assert co_lookup_limits(
        "command-a-reasoning-08-2025", "payg",
    )["rpm"] == 20
    assert co_lookup_limits(
        "rerank-v4.0-pro", "free",
    )["rpm"] == 10
    assert co_lookup_limits("unknown", "free") == {}


def test_cohere_summary_rows_free() -> None:
    rows = co_summary_quota_rows(
        {
            "command-a-reasoning-08-2025": {
                "tokens": 100, "requests": 2,
            },
        },
        month_used=40,
        account_type="free",
    )
    by_name = {r["name"]: r for r in rows}
    assert by_name["requests (last 60s)"]["used"] == 2
    assert by_name["tokens (last 60s)"]["used"] == 100
    assert by_name["calls (month)"]["used"] == 40
    assert by_name["calls (month)"]["total"] == 1000


def test_cohere_summary_rows_payg_no_monthly() -> None:
    rows = co_summary_quota_rows(
        {
            "command-a-03-2025": {
                "tokens": 1, "requests": 1,
            },
        },
        month_used=999,
        account_type="payg",
    )
    names = {r["name"] for r in rows}
    assert "calls (month)" not in names
    assert len(rows) == 2


def test_cohere_local_usage_detail() -> None:
    rows = co_apply_local_usage(
        "free",
        {
            "command-a-reasoning-08-2025": {
                "tokens": 0, "requests": 3,
            },
        },
        {
            "command-a-reasoning-08-2025": {
                "tokens": 1000, "requests": 34,
            },
        },
    )
    rpm = next(
        r for r in rows
        if r["name"] == (
            "command-a-reasoning-08-2025 requests (RPM)"
        )
    )
    today = next(
        r for r in rows
        if r["name"] == (
            "command-a-reasoning-08-2025 requests (today)"
        )
    )
    assert rpm["used"] == 3
    assert rpm["total"] == 20
    assert today["used"] == 34
    assert today["unlimited"] is True


def test_cohere_quotas_from_headers() -> None:
    headers = {
        "x-ratelimit-limit-requests": "20",
        "x-ratelimit-remaining-requests": "17",
    }
    rows = co_quotas_from_headers(
        headers, "command-a-reasoning-08-2025", "free",
    )
    assert rows
    assert rows[0]["used"] == 3
    assert rows[0]["total"] == 20
    assert "command-a-reasoning-08-2025" in rows[0]["name"]


# ──────────────────────────────────────────────
# Morph
# ──────────────────────────────────────────────


def test_morph_handler_registered() -> None:
    handler = get_usage_handler("morph")
    assert handler is not None
    assert isinstance(handler, MorphUsageHandler)


def test_morph_config_limits_no_invented_rows() -> None:
    limits = MorphConfig().RATE_LIMITS
    assert limits["free"] == {"calls": 200}
    assert limits["payg"] == {}
    assert limits["subscribe"] == {}
    assert set(limits) == {"free", "payg", "subscribe"}
    assert "rpm" not in limits["free"]
    assert "rpd" not in limits["free"]
    assert "tpm" not in limits["free"]
    assert "tpd" not in limits["free"]


def test_morph_monthly_bar_local_used() -> None:
    bar = morph_monthly_bar(
        37, reset_at="2026-09-01T00:00:00+00:00",
    )
    assert bar["name"] == "Morph monthly free requests"
    assert bar["used"] == 37
    assert bar["total"] == 200
    assert bar["remaining"] == 163
    assert bar["unlimited"] is False


def test_morph_monthly_bar_cap_reached() -> None:
    bar = morph_monthly_bar(200, reset_at=None)
    assert bar["used"] == 200
    assert bar["remaining"] == 0
    assert bar["remaining_percentage"] == 0.0


def test_morph_fetch_free_local_used() -> None:
    handler = MorphUsageHandler()
    with patch(
        "app.providers.morph.quota.count_requests_since",
        new_callable=AsyncMock,
        return_value=41,
    ):
        result = asyncio.run(handler.fetch(
            "tok", {"accountType": "free"}, "conn-1",
        ))
    assert result.plan == "free"
    assert len(result.quotas) == 1
    quota = result.quotas[0]
    assert quota.name == "Morph monthly free requests"
    assert quota.used == 41
    assert quota.total == 200
    assert quota.reset_at is not None
    assert result.limit_reached is False
    assert result.message is not None
    assert "200 requests per month" in result.message


def test_morph_fetch_free_cap_reached() -> None:
    handler = MorphUsageHandler()
    with patch(
        "app.providers.morph.quota.count_requests_since",
        new_callable=AsyncMock,
        return_value=200,
    ):
        result = asyncio.run(handler.fetch(
            "tok", {"accountType": "free"}, "conn-1",
        ))
    assert result.limit_reached is True
    assert result.quotas[0].remaining == 0


def test_morph_payg_no_bar() -> None:
    handler = MorphUsageHandler()
    result = asyncio.run(handler.fetch(
        "tok", {"accountType": "payg"}, "conn-1",
    ))
    assert result.quotas == []
    assert result.limit_reached is False
    assert result.message is not None
    assert "no numeric" in result.message


def test_morph_subscribe_no_bar() -> None:
    handler = MorphUsageHandler()
    result = asyncio.run(handler.fetch(
        "tok", {"accountType": "subscribe"}, "conn-1",
    ))
    assert result.plan == "subscribe"
    assert result.quotas == []


def test_morph_count_requests_since_local_db() -> None:
    fake_db = MagicMock()
    fake_result = MagicMock()
    fake_result.scalar.return_value = 12
    fake_db.execute = AsyncMock(return_value=fake_result)
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=fake_db)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    with patch(
        "app.database.async_session",
        return_value=session_cm,
    ):
        used = asyncio.run(morph_count_requests_since(
            datetime(2026, 8, 1, tzinfo=timezone.utc),
            "abc-123",
        ))
    assert used == 12


# ──────────────────────────────────────────────
# DeepSeek
# ──────────────────────────────────────────────


def test_deepseek_config_signup_grant() -> None:
    limits = DeepseekConfig().RATE_LIMITS
    assert limits["signup_grant"] == {
        "tokens": 5_000_000,
        "days": 30,
        "value_usd_cents": 840,
    }
    assert lookup_concurrency("deepseek-v4-flash") == 2500
    assert lookup_concurrency("ds/deepseek-v4-pro") == 500
    assert "rpm" not in limits["signup_grant"]
    assert resolve_plan(None) == "free"
    assert resolve_plan({"accountType": "free"}) == "free"
    assert resolve_plan({"accountType": "payg"}) == "payg"


def test_deepseek_balance_rows() -> None:
    reset_at = "2026-09-25T00:00:00+00:00"
    rows = balance_quota_rows({
        "is_available": True,
        "balance_infos": [{
            "currency": "USD",
            "total_balance": "6.12",
            "granted_balance": "6.12",
            "topped_up_balance": "0.00",
        }],
    }, reset_at=reset_at)
    assert len(rows) == 1
    granted = rows[0]
    assert granted["name"] == "Granted balance (USD)"
    assert granted["remaining"] == 612
    assert granted["total"] == 840
    assert granted["used"] == 228
    assert granted["reset_at"] == reset_at

    wallet = balance_quota_rows({
        "balance_infos": [{
            "currency": "USD",
            "total_balance": "3.15",
            "granted_balance": "0.00",
            "topped_up_balance": "3.15",
        }],
    }, free_summary=True)
    assert len(wallet) == 1
    assert wallet[0]["name"] == "API balance (USD)"
    assert wallet[0]["remaining"] == 315

    topped = balance_quota_rows({
        "balance_infos": [{
            "currency": "USD",
            "total_balance": "10.50",
            "granted_balance": "0.00",
            "topped_up_balance": "10.50",
        }],
    })
    assert topped[0]["name"] == "API balance (USD)"
    assert topped[0]["remaining"] == 1050


def test_deepseek_usage_fetch() -> None:
    handler = DeepseekUsageHandler()
    mock_resp = _mock_response(200, {
        "is_available": True,
        "balance_infos": [{
            "currency": "USD",
            "total_balance": "6.12",
            "granted_balance": "6.12",
            "topped_up_balance": "0.00",
        }],
    })

    async def _run() -> None:
        with patch.object(
            handler, "_get", new_callable=AsyncMock,
            return_value=mock_resp,
        ), patch(
            "app.providers.deepseek.quota.lifetime_tokens",
            new_callable=AsyncMock,
            return_value=1_250_000,
        ), patch(
            "app.providers.deepseek.quota.grant_expires_at",
            new_callable=AsyncMock,
            return_value="2026-09-25T00:00:00+00:00",
        ):
            return await handler.fetch(
                "sk-test",
                provider_data={"accountType": "free"},
                connection_id="c1",
            )

    result = asyncio.run(_run())
    assert result.plan == "free"
    assert result.limit_reached is False
    assert len(result.quotas) == 2
    tokens = result.quotas[0]
    assert tokens.name == "Signup grant tokens"
    assert tokens.used == 1_250_000
    assert tokens.total == signup_token_grant()
    assert tokens.reset_at == "2026-09-25T00:00:00+00:00"
    assert result.quotas[1].name == "API balance (USD)"


def test_deepseek_usage_reads_api_key_from_provider_data() -> None:
    handler = DeepseekUsageHandler()
    mock_resp = _mock_response(200, {
        "is_available": True,
        "balance_infos": [{
            "currency": "USD",
            "granted_balance": "1.00",
            "topped_up_balance": "0.00",
        }],
    })

    async def _run() -> None:
        with patch.object(
            handler, "_get", new_callable=AsyncMock,
            return_value=mock_resp,
        ) as get_mock, patch(
            "app.providers.deepseek.quota.lifetime_tokens",
            new_callable=AsyncMock,
            return_value=0,
        ), patch(
            "app.providers.deepseek.quota.grant_expires_at",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await handler.fetch(
                "",
                provider_data={
                    "accountType": "free",
                    "apiKey": "sk-from-blob",
                },
                connection_id="c1",
            )
            get_mock.assert_called_once()
            headers = get_mock.call_args[0][1]
            assert headers["Authorization"] == "Bearer sk-from-blob"
            return result

    result = asyncio.run(_run())
    assert result.plan == "free"
    assert len(result.quotas) >= 1


def test_deepseek_usage_missing_api_key() -> None:
    handler = DeepseekUsageHandler()

    async def _run() -> UsageResponse:
        with patch(
            "app.providers.deepseek.quota.lifetime_tokens",
            new_callable=AsyncMock,
            return_value=42,
        ), patch(
            "app.providers.deepseek.quota.grant_expires_at",
            new_callable=AsyncMock,
            return_value="2026-09-25T00:00:00+00:00",
        ):
            return await handler.fetch(
                "",
                provider_data={"accountType": "free"},
                connection_id="c1",
            )

    result = asyncio.run(_run())
    assert result.plan == "free"
    assert result.message == "No API key found on this connection."
    assert len(result.quotas) == 1
    assert result.quotas[0].used == 42


def test_commandcode_handler_registered() -> None:
    from app.providers.commandcode.quota import CommandcodeUsageHandler

    handler = get_usage_handler("commandcode")
    assert handler is not None
    assert isinstance(handler, CommandcodeUsageHandler)


def test_commandcode_lookup_limits() -> None:
    from app.providers.commandcode.quota import lookup_limits

    assert lookup_limits("pro")["monthly"] == 80
    assert lookup_limits("provider") == {}
