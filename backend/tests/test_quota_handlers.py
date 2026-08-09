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
from app.services.quota.github import GitHubUsageHandler
from app.services.quota.claude import ClaudeUsageHandler
from app.services.quota.codex import CodexUsageHandler
from app.services.quota.kiro import KiroUsageHandler
from app.services.quota.qoder import QoderUsageHandler


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
    mock_resp = _mock_response(200, {
        "quotas": {
            "user": {
                "total": 1000,
                "used": 350,
                "remaining": 650,
                "resetAt": "2026-08-01T00:00:00Z",
            },
            "organization": {
                "total": 5000,
                "used": 1200,
                "remaining": 3800,
            },
        },
    })

    with patch.object(
        handler, "_get", new_callable=AsyncMock,
        return_value=mock_resp,
    ):
        result = await handler.fetch("fake-token")

    assert len(result.quotas) == 2

    user = next(
        q for q in result.quotas if q.name == "User"
    )
    assert user.used == 350
    assert user.total == 1000
    assert user.remaining == 650
    assert user.remaining_percentage == 65.0


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
