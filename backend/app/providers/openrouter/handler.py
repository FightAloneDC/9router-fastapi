"""OpenRouter handler — extra headers (HTTP-Referer, X-Title)."""

from app.providers.base import BaseProviderHandler, ValidateResult


class OpenrouterHandler(BaseProviderHandler):
    """Handler for OpenRouter provider (extra headers support)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data) or "https://openrouter.ai/api/v1"

        # Build extra headers from connection data
        extra_headers = {}
        if data:
            if data.get("httpReferer"):
                extra_headers["HTTP-Referer"] = data["httpReferer"]
            if data.get("xTitle"):
                extra_headers["X-Title"] = data["xTitle"]

        # Temporarily inject extra headers for validation
        original = self.config.EXTRA_HEADERS
        self.config = type(self.config)(
            **{**self.config.model_dump(), "EXTRA_HEADERS": {**self.config.EXTRA_HEADERS, **extra_headers}}
        )
        try:
            result = await self._validate_openai_compatible(api_key, base_url, data)
        finally:
            self.config = type(self.config)(
                **{**self.config.model_dump(), "EXTRA_HEADERS": original}
            )
        return result
