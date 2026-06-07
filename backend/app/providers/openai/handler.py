"""OpenAI handler — Bearer auth + /audio/speech endpoint."""

from __future__ import annotations

import io
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler

# MIME mapping for TTS response formats
_FORMAT_TO_MIME: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/L16",
}


class OpenaiHandler(BaseProviderHandler):
    """Handler for OpenAI provider."""

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
        extra_headers: dict | None = None,
        **_kwargs,
    ) -> tuple[bytes, str]:
        """OpenAI-compatible /audio/speech endpoint."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        body: dict = {
            "model": tts_model,
            "voice": voice,
            "input": input_text,
            "response_format": response_format,
        }
        if speed is not None:
            body["speed"] = speed

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/audio/speech"
        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type") or _FORMAT_TO_MIME.get(response_format, "audio/mpeg")
        return resp.content, content_type

    async def execute_stt(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
        prompt: str | None = None,
        response_format: str | None = None,
        temperature: float | None = None,
        **_kwargs,
    ) -> dict[str, Any]:
        """OpenAI Whisper-compatible multipart transcription."""
        if not model:
            raise ValueError("STT model is required")

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
        data: dict[str, str] = {"model": model}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        if response_format:
            data["response_format"] = response_format
        if temperature is not None:
            data["temperature"] = str(temperature)

        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()

        if response_format in ("text", "srt", "vtt"):
            return {"text": resp.text}

        return resp.json()
