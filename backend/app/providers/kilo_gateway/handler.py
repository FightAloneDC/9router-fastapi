"""Kilo Gateway handler — OpenAI-compatible validation."""

from app.providers.base import BaseProviderHandler, ValidateResult


class KiloGatewayHandler(BaseProviderHandler):
    """Handler for Kilo Gateway provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Kilo Gateway")
        base_url = self._resolve_base_url(data)
        if not base_url:
            return ValidateResult(valid=False, error="Base URL is required")
        return await self._validate_openai_compatible(api_key, base_url, data)
