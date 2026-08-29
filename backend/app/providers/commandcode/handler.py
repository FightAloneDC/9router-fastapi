"""Command Code handler — hybrid OpenAI + Anthropic upstream paths."""

from __future__ import annotations

from app.providers.base import BaseProviderHandler, ValidateResult
from app.providers.commandcode.config import (
    CLAUDE_MODEL_PREFIX,
    PLANS_WITHOUT_PROVIDER_API,
)
from app.providers.commandcode.quota import studio_plan_from_data


def strip_alias_model_id(model: str, alias: str) -> str:
    """Remove ``alias/`` prefix from a routed model id."""
    mid = (model or "").strip()
    prefix = f"{alias}/"
    if mid.startswith(prefix):
        return mid[len(prefix):]
    return mid


def is_claude_catalog_model(model: str, alias: str = "cmc") -> bool:
    """True when upstream expects Anthropic Messages for this id."""
    mid = strip_alias_model_id(model, alias)
    return mid.startswith(CLAUDE_MODEL_PREFIX)


class CommandcodeHandler(BaseProviderHandler):
    """Hybrid router: Claude ids → /messages, others → /chat/completions."""

    def resolve_upstream_format(self, model: str = "") -> str:
        if is_claude_catalog_model(model, self.config.ALIAS):
            return "claude"
        return "openai"

    def build_upstream_url(
        self,
        base_url: str,
        stream: bool = False,
        data: dict | None = None,
        model: str = "",
    ) -> str:
        base = base_url.rstrip("/")
        if is_claude_catalog_model(model, self.config.ALIAS):
            return f"{base}/messages"
        return f"{base}/chat/completions"

    async def validate(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> ValidateResult:
        if not api_key:
            return ValidateResult(
                valid=False,
                error="No API key configured",
            )

        plan = studio_plan_from_data(data)
        if plan in PLANS_WITHOUT_PROVIDER_API:
            return ValidateResult(
                valid=False,
                error=(
                    "Go plan does not include Provider API "
                    "(403 upgrade_required). Set studioPlan to GOAT "
                    "or higher, or upgrade on commandcode.ai."
                ),
            )

        result = await super().validate(api_key, data)
        if result.valid:
            return result

        err = (result.error or "").lower()
        if "403" in err or "forbidden" in err:
            return ValidateResult(
                valid=False,
                error=(
                    "API access denied (403). Go plan has no API "
                    "— upgrade to GOAT or higher."
                ),
                latency_ms=result.latency_ms,
            )

        return result
