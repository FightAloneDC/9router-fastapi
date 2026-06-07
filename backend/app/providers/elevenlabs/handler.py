"""ElevenLabs handler — xi-api-key auth + /voices endpoint."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class ElevenlabsHandler(BaseProviderHandler):
    """Handler for ElevenLabs provider."""

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        response_format: str = "mp3",
        **_kwargs,
    ) -> tuple[bytes, str]:
        """ElevenLabs TTS — voice ID in URL path, xi-api-key auth."""
        base_url = self._resolve_base_url(None)
        url = f"{base_url}/text-to-speech/{voice}"
        headers = {
            self.config.AUTH_HEADER: api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        body = {
            "text": input_text,
            "model_id": tts_model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = await client.post(url, json=body, headers=headers)
        if not resp.is_success:
            try:
                err = resp.json()
                msg = (err.get("detail") or {}).get("message") or err.get("detail") or ""
            except Exception:
                msg = ""
            raise ValueError(msg or f"ElevenLabs TTS failed: {resp.status_code}")

        audio = resp.content
        if len(audio) < 1024:
            raise ValueError("ElevenLabs TTS returned empty/truncated audio (< 1KB)")
        return audio, "audio/mpeg"

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Fetch ElevenLabs voices via GET /v1/voices."""
        if not api_key:
            raise ValueError("ElevenLabs requires an API key")
        base_url = self.config.BASE_URL.rstrip("/")
        resp = await client.get(
            f"{base_url}/voices",
            headers={self.config.AUTH_HEADER: api_key},
        )
        resp.raise_for_status()

        voices: list[dict[str, Any]] = []
        for v in resp.json().get("voices", []) or []:
            voices.append({
                "id": v.get("voice_id", ""),
                "name": v.get("name", ""),
                "lang": v.get("labels", {}).get("language", "en"),
                "gender": v.get("labels", {}).get("gender", ""),
            })
        return voices

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for ElevenLabs")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/voices"
        headers = {self.config.AUTH_HEADER: api_key}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"ElevenLabs returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                voices = resp.json().get("voices", [])
                models = [v.get("voice_id", "") for v in voices if v.get("voice_id")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to ElevenLabs API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
