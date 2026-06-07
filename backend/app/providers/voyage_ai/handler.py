"""Voyage AI handler — embedding test call for validation."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class VoyageAiHandler(BaseProviderHandler):
    """Handler for Voyage AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Voyage AI")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/embeddings"
        headers = {
            self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json={"input": "ping", "model": "voyage-3"})
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Voyage returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Voyage AI API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
