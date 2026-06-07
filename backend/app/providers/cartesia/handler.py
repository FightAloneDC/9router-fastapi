"""Cartesia handler — X-API-Key auth + Cartesia-Version header."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class CartesiaHandler(BaseProviderHandler):
    """Handler for Cartesia TTS provider."""

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
        """Cartesia TTS — X-API-Key auth, Cartesia-Version header."""
        if not tts_model:
            raise ValueError("Cartesia TTS requires a model (e.g. 'sonic-2')")

        base_url = self._resolve_base_url(None)
        headers = {
            self.config.AUTH_HEADER: api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json",
        }
        body: dict = {
            "model_id": tts_model,
            "transcript": input_text,
            "output_format": {"container": "mp3", "bit_rate": 128000, "sample_rate": 44100},
        }
        if voice:
            body["voice"] = {"mode": "id", "id": voice}

        resp = await client.post(base_url, json=body, headers=headers)
        if not resp.is_success:
            raise ValueError(f"Cartesia TTS failed: {resp.status_code} — {resp.text[:300]}")
        if not resp.content:
            raise ValueError("Cartesia TTS returned empty audio")
        content_type = resp.headers.get("content-type") or "audio/mpeg"
        return resp.content, content_type
