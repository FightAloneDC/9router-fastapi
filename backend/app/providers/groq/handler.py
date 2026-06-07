"""Groq handler — Bearer auth + OpenAI-compatible endpoints."""

from __future__ import annotations

import io
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class GroqHandler(BaseProviderHandler):
    """Handler for Groq provider."""

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
        """Groq Whisper-compatible multipart transcription."""
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
