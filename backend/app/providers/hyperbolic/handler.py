"""Hyperbolic handler — base64 JSON TTS response."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class HyperbolicHandler(BaseProviderHandler):
    """Handler for Hyperbolic provider."""

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        **_kwargs,
    ) -> tuple[bytes, str]:
        """Hyperbolic /audio/generation — returns ``{"audio": <base64>}`` JSON."""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": tts_model, "text": input_text, "language": voice,
            "speaker": "EN-Default", "sdp_ratio": 0.5, "noise_scale": 0.6,
            "noise_scale_w": 0.8, "speed": 1.0,
        }
        base_url = self._resolve_base_url(None)
        resp = await client.post(f"{base_url}/audio/generation", json=body, headers=headers)
        resp.raise_for_status()

        data = resp.json()
        audio_b64 = data.get("audio") or data.get("data", {}).get("audio")
        if not audio_b64:
            raise ValueError(f"Hyperbolic response missing audio field: {data!r}"[:300])
        return base64.b64decode(audio_b64), "audio/mpeg"
