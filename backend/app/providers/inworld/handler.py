"""Inworld handler — Basic auth + /voices endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class InworldHandler(BaseProviderHandler):
    """Handler for Inworld provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Inworld")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(
                    "https://api.inworld.ai/tts/v1/voices",
                    headers={"Authorization": f"Basic {api_key}"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Inworld returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                voices = resp.json().get("voices", [])
                models = [v.get("voiceId", "") for v in voices if v.get("voiceId")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Inworld API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
