"""Kilocode handler — OAuth token validation via /api/profile."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class KilocodeHandler(BaseProviderHandler):
    """Handler for Kilo Code (OAuth device-code flow).

    Validates token via GET /api/profile — NOT /models.
    """

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No access token configured")

        start = time.monotonic()
        base_url = self._resolve_base_url(data)
        url = f"{base_url}/api/profile"

        try:
            async with create_upstream_client(timeout=15.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    return ValidateResult(valid=True, latency_ms=latency)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Token invalid or revoked", latency_ms=latency)
                return ValidateResult(valid=False, error=f"API returned {resp.status_code}", latency_ms=latency)
        except httpx.ConnectError:
            return ValidateResult(valid=False, error="Cannot connect to Kilo Code API", latency_ms=int((time.monotonic() - start) * 1000))
        except httpx.TimeoutException:
            return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
        except Exception as e:
            return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        """Fetch free models from Kilo public gateway (no auth)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://api.kilo.ai/api/gateway/models", headers={"Accept": "application/json"})
            resp.raise_for_status()
            all_models = resp.json().get("data", [])
            return [
                {"id": m["id"], "name": m.get("name", m["id"]), "type": "llm"}
                for m in all_models
                if m.get("id") and m.get("isFree", False)
            ]
