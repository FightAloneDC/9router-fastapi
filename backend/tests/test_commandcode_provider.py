"""Tests for Command Code provider handler and config."""

import asyncio

from app.providers.base import ValidateResult
from app.providers.commandcode.config import CommandcodeConfig
from app.providers.commandcode.handler import (
    CommandcodeHandler,
    is_claude_catalog_model,
    strip_alias_model_id,
)
from app.providers.commandcode.quota import (
    CommandcodeUsageHandler,
    lookup_limits,
    published_credit_bars,
    resolve_plan,
    studio_plan_from_data,
)
from app.providers.provider import Provider
from app.routers.providers.helpers import normalize_studio_plan_for_provider


def test_base_url() -> None:
    cfg = CommandcodeConfig()
    assert cfg.BASE_URL == "https://api.commandcode.ai/provider/v1"
    assert cfg.MODEL_CATALOG_TABLE is True


def test_strip_alias() -> None:
    assert strip_alias_model_id("cmc/gpt-5", "cmc") == "gpt-5"
    assert strip_alias_model_id("gpt-5", "cmc") == "gpt-5"


def test_claude_model_detection() -> None:
    assert is_claude_catalog_model("claude-sonnet-5")
    assert is_claude_catalog_model("cmc/claude-opus-5")
    assert not is_claude_catalog_model("gpt-5.6-sol-medium")
    assert not is_claude_catalog_model("cmc/deepseek/deepseek-v3")


def test_resolve_upstream_format() -> None:
    handler = CommandcodeHandler(CommandcodeConfig())
    assert handler.resolve_upstream_format("claude-sonnet-5") == "claude"
    assert handler.resolve_upstream_format("cmc/claude-opus-5") == "claude"
    assert handler.resolve_upstream_format("gpt-5.6-sol-medium") == "openai"


def test_build_upstream_url() -> None:
    handler = CommandcodeHandler(CommandcodeConfig())
    base = "https://api.commandcode.ai/provider/v1"
    assert handler.build_upstream_url(
        base, model="claude-sonnet-5",
    ).endswith("/messages")
    assert handler.build_upstream_url(
        base, model="gpt-5.6-sol-medium",
    ).endswith("/chat/completions")


def test_provider_loads_custom_handler() -> None:
    handler = Provider("commandcode").handler()
    assert isinstance(handler, CommandcodeHandler)


def test_rate_limits_go() -> None:
    limits = lookup_limits("go")
    assert limits["monthly"] == 10
    assert limits["window_5h"] == 3
    assert limits["weekly"] == 6


def test_rate_limits_goat() -> None:
    limits = lookup_limits("goat")
    assert limits["monthly"] == 70
    assert limits["window_5h"] == 14
    assert limits["weekly"] == 35


def test_resolve_plan_aliases_only() -> None:
    assert resolve_plan("max10") == "max_10x"
    assert resolve_plan("team") == "team_pro"
    assert resolve_plan("pro") == "pro"
    assert resolve_plan("free") is None
    assert resolve_plan("payg") is None
    assert resolve_plan("subscribe") is None


def test_studio_plan_from_data() -> None:
    assert studio_plan_from_data({"studioPlan": "max10"}) == "max_10x"
    assert studio_plan_from_data({"accountType": "free"}) is None


def test_normalize_studio_plan_for_provider() -> None:
    assert normalize_studio_plan_for_provider("commandcode", "goat") == "goat"
    assert normalize_studio_plan_for_provider("commandcode", "max10") == "max_10x"


def test_published_credit_bars() -> None:
    rows = published_credit_bars(lookup_limits("pro"))
    assert len(rows) == 3
    assert rows[0]["total"] == 8000
    assert rows[0]["used"] == 0


def test_plans_without_provider_api() -> None:
    from app.providers.commandcode.config import PLANS_WITHOUT_PROVIDER_API

    assert "go" in PLANS_WITHOUT_PROVIDER_API
    assert "goat" not in PLANS_WITHOUT_PROVIDER_API


async def _validate_go_plan() -> ValidateResult:
    handler = CommandcodeHandler(CommandcodeConfig())
    return await handler.validate("sk-test", {"studioPlan": "go"})


def test_validate_go_plan_rejects_api() -> None:
    resp = asyncio.run(_validate_go_plan())
    assert isinstance(resp, ValidateResult)
    assert resp.valid is False
    assert "403" in (resp.error or "")


def test_quota_fetch_go_plan() -> None:
    async def _run():
        handler = CommandcodeUsageHandler()
        return await handler.fetch("key", {"studioPlan": "go"})

    resp = asyncio.run(_run())
    assert resp.plan == "go"
    assert resp.quotas == []
    assert "403" in (resp.message or "")


def test_quota_fetch_pro_plan() -> None:
    async def _run():
        handler = CommandcodeUsageHandler()
        return await handler.fetch("key", {"studioPlan": "pro"})

    resp = asyncio.run(_run())
    assert len(resp.quotas) == 3
    assert resp.quotas[0].total == 8000


def test_quota_missing_studio_plan() -> None:
    async def _run():
        handler = CommandcodeUsageHandler()
        return await handler.fetch("key", {"accountType": "free"})

    resp = asyncio.run(_run())
    assert resp.plan is None
    assert "studioPlan" in (resp.message or "")
