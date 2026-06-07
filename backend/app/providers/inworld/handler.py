"""Inworld handler — Basic auth + /voices endpoint."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class InworldHandler(BaseProviderHandler):
    """Handler for Inworld provider."""

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
        """Inworld TTS — POST {base_url}, Basic auth, base64 JSON response."""
        import base64

        base_url = self._resolve_base_url(None)
        headers = {
            self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "text": input_text,
            "voiceId": voice or "Alex",
            "modelId": tts_model or "inworld-tts-1.5-mini",
            "audioConfig": {"audioEncoding": "MP3"},
        }
        resp = await client.post(base_url, json=body, headers=headers)
        if not resp.is_success:
            raise ValueError(f"Inworld TTS failed: {resp.status_code} — {resp.text[:300]}")
        data = resp.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise ValueError("Inworld TTS returned no audioContent")
        return base64.b64decode(audio_b64), "audio/mpeg"

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Fetch Inworld TTS voices via GET /tts/v1/voices."""
        if not api_key:
            raise ValueError("Inworld requires an API key")
        base_url = self.config.BASE_URL.rstrip("/")
        resp = await client.get(
            f"{base_url}/tts/v1/voices",
            headers={self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}"},
        )
        resp.raise_for_status()

        voices: list[dict[str, Any]] = []
        for v in resp.json().get("voices", []) or []:
            langs = v.get("languages", ["en"]) or ["en"]
            voice_id = v.get("voiceId", "")
            for lang in langs:
                voices.append({
                    "id": voice_id,
                    "name": v.get("displayName", voice_id),
                    "lang": lang,
                    "gender": v.get("gender", ""),
                })
        return voices

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Inworld")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/tts/v1/voices"
        headers = {self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}"}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
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
