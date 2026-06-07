"""OpenRouter handler — extra headers (HTTP-Referer, X-Title)."""

from app.providers.base import BaseProviderHandler, ValidateResult


class OpenrouterHandler(BaseProviderHandler):
    """Handler for OpenRouter provider (extra headers support)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data) or "https://openrouter.ai/api/v1"

        extra_headers = {}
        if data:
            if data.get("httpReferer"):
                extra_headers["HTTP-Referer"] = data["httpReferer"]
            if data.get("xTitle"):
                extra_headers["X-Title"] = data["xTitle"]

        return await self._validate_openai_compatible(api_key, base_url, data, extra_headers=extra_headers)
