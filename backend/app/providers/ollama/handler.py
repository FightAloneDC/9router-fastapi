"""Ollama handler — /api/tags endpoint, no auth."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class OllamaHandler(BaseProviderHandler):
    """Handler for Ollama provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        base_url = self._resolve_base_url(data) or "http://localhost:11434"

        start = time.monotonic()
        url = f"{base_url}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Ollama returned {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = [m.get("name", "") for m in data_resp.get("models", []) if m.get("name")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to Ollama at {base_url}. Is it running?", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        base_url = self._resolve_base_url(data) or "http://localhost:11434"
        url = f"{base_url}/api/tags"

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data_resp = resp.json()
            models = []
            for m in data_resp.get("models", []):
                name = m.get("name", "")
                if name:
                    models.append({"id": name, "name": name})
            return [self._normalize_model(m) for m in models if self._normalize_model(m).get("id")]
