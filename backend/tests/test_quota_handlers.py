"""Tests for quota usage handlers.

Validates that each provider handler correctly parses
API responses into standardized UsageResponse format.
"""

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
from app.providers.qoder.quota import QoderUsageHandler
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
