"""PlayHT handler — X-USER-ID + Bearer auth."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class PlayhtHandler(BaseProviderHandler):
    """Handler for PlayHT TTS provider."""

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
        """PlayHT TTS — api_key is 'userId:apiKey' colon-joined."""
        user_id, _, key = (api_key or "").partition(":")
        if not user_id or not key:
            raise ValueError("PlayHT TTS requires apiKey in 'userId:apiKey' format")
        if not voice:
            raise ValueError("PlayHT TTS requires a voice (S3 manifest URL)")

        base_url = self._resolve_base_url(None)
        headers = {
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
            "X-USER-ID": user_id,
            "Authorization": f"Bearer {key}",
        }
        body = {
            "text": input_text,
            "voice": voice,
            "voice_engine": tts_model or "PlayDialog",
            "output_format": "mp3",
            "speed": 1,
        }
        resp = await client.post(base_url, json=body, headers=headers)
        if not resp.is_success:
            raise ValueError(f"PlayHT TTS failed: {resp.status_code} — {resp.text[:300]}")
        if not resp.content:
            raise ValueError("PlayHT TTS returned empty audio")
        return resp.content, "audio/mpeg"
