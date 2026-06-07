"""SiliconFlow handler — OpenAI-compatible TTS."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler

_FORMAT_TO_MIME: dict[str, str] = {
    "mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/opus",
    "aac": "audio/aac", "flac": "audio/flac", "pcm": "audio/L16",
}


class SiliconflowHandler(BaseProviderHandler):
    """Handler for SiliconFlow provider."""

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        response_format: str = "mp3",
        speed: float | None = None,
        **_kwargs,
    ) -> tuple[bytes, str]:
        """SiliconFlow OpenAI-compatible /audio/speech endpoint."""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body: dict = {"model": tts_model, "voice": voice, "input": input_text, "response_format": response_format}
        if speed is not None:
            body["speed"] = speed

        base_url = self._resolve_base_url(None)
        resp = await client.post(f"{base_url}/audio/speech", json=body, headers=headers)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type") or _FORMAT_TO_MIME.get(response_format, "audio/mpeg")
        return resp.content, content_type
