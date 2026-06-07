"""Anthropic provider handler — x-api-key auth + custom validation."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AnthropicHandler(BaseProviderHandler):
    """Handler for Anthropic provider (x-api-key auth)."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data)
        if base_url:
            url = base_url.rstrip("/")
            if url.endswith("/messages"):
                url = url[:-9]
            url = f"{url}/models"
        else:
            url = "https://api.anthropic.com/v1/models"

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Server error ({resp.status_code})", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to provider", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

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
            BASE_URL=base_url or "https://api.anthropic.com/v1",
            AUTH_HEADER="x-api-key",
            AUTH_PREFIX="",
            EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        )
        models_raw = await fetch_models_header_auth(config, api_key)
        return [self._normalize_model(m) for m in models_raw if self._normalize_model(m).get("id")]

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Anthropic uses /messages endpoint."""
        return f"{base_url.rstrip('/')}/messages"
