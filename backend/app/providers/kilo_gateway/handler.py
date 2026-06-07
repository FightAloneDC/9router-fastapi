"""Kilo Gateway handler — openai-chat validation type with custom error parsing."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class KiloGatewayHandler(BaseProviderHandler):
    """Handler for Kilo Gateway provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Kilo Gateway")

        base_url = self._resolve_base_url(data)
        if not base_url:
            return ValidateResult(valid=False, error="Base URL is required")

        start = time.monotonic()
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = resp_data.get("error", {}).get("message", f"Kilo Gateway returned {resp.status_code}") if isinstance(resp_data.get("error"), dict) else f"Kilo Gateway returned {resp.status_code}"
                    return ValidateResult(valid=False, error=error_msg, latency_ms=latency)
                data_resp = resp.json()
                models = [m.get("id") for m in data_resp.get("data", []) if isinstance(m, dict)]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Kilo Gateway API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
