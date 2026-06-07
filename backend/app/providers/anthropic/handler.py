"""Anthropic provider handler — x-api-key auth + custom validation."""

from app.providers.base import BaseProviderHandler, ValidateResult


class AnthropicHandler(BaseProviderHandler):
    """Handler for Anthropic provider (x-api-key auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data)
        if base_url.endswith("/messages"):
            base_url = base_url[:-9]

        return await self._validate_anthropic_compatible(api_key, base_url)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_header_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        base_url = self._resolve_base_url(data)
        config = BaseProviderConfig(
            PROVIDER_NAME="Anthropic",
            PROVIDER_ID="anthropic",
            ALIAS="an",
            BASE_URL=base_url or self.config.BASE_URL,
            AUTH_HEADER="x-api-key",
            AUTH_PREFIX="",
            EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        )
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Anthropic uses /messages endpoint."""
        return f"{base_url.rstrip('/')}/messages"
