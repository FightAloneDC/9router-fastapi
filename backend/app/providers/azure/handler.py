"""Azure OpenAI provider handler — api-key header + deployment URL."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AzureHandler(BaseProviderHandler):
    """Handler for Azure OpenAI provider."""

    def _resolve_base_url(self, data: dict | None = None) -> str:
        """Azure uses azureEndpoint from providerSpecificData."""
        if data:
            endpoint = data.get("azureEndpoint") or data.get("endpoint") or ""
            if endpoint:
                return endpoint.rstrip("/")
        return super()._resolve_base_url(data)

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        data = data or {}
        endpoint = (data.get("azureEndpoint") or data.get("endpoint") or "").rstrip("/")
        deployment = data.get("deployment") or ""
        api_version = data.get("apiVersion") or "2024-02-15-preview"

        if not endpoint:
            return ValidateResult(valid=False, error="Azure endpoint URL is required")
        if not deployment:
            return ValidateResult(valid=False, error="Azure deployment name is required")

        start = time.monotonic()
        url = f"{endpoint}/openai/deployments?api-version={api_version}"
        headers = {"api-key": api_key}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Azure returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to {endpoint}", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
