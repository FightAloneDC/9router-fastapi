"""Tests for quota usage handlers.

Validates that each provider handler correctly parses
API responses into standardized UsageResponse format.
"""

import pytest
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
    quotas_from_headers as nv_quotas_from_headers,
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
    rpm = next(r for r in rows if "RPM" in r["name"])
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
