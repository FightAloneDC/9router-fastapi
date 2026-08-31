"""OpenRouter handler — extra headers (HTTP-Referer, X-Title)."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult

_FORMAT_TO_MIME: dict[str, str] = {
    "mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/opus",
    "aac": "audio/aac", "flac": "audio/flac", "pcm": "audio/L16",
}


class OpenrouterHandler(BaseProviderHandler):
    """Handler for OpenRouter provider (extra headers support)."""

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        response_format: str = "wav",
        **_kwargs,
    ) -> tuple[bytes, str]:
        """OpenRouter TTS — via chat completions w/ audio modality, SSE stream."""
        base_url = self._resolve_base_url(None)
        url = f"{base_url}/chat/completions"
        fmt = response_format if response_format in {"wav", "mp3", "flac", "opus", "pcm16"} else "wav"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://9router.local",
            "X-Title": "9Router",
        }
        body = {
            "model": tts_model,
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": fmt},
            "stream": True,
            "messages": [{"role": "user", "content": input_text}],
        }

        chunks: list[str] = []
        async with client.stream("POST", url, json=body, headers=headers) as resp:
            if not resp.is_success:
                await resp.aread()
                try:
                    err = resp.json()
                    msg = (err.get("error") or {}).get("message", "")
                except Exception:
                    msg = ""
                raise ValueError(msg or f"OpenRouter TTS failed: {resp.status_code}")

            buffer = ""
            async for raw in resp.aiter_text():
                buffer += raw
                lines = buffer.split("\n")
                buffer = lines.pop()
                for line in lines:
                    line = line.strip()
                    if not line.startswith("data: ") or line == "data: [DONE]":
                        continue
                    try:
                        payload = json.loads(line[6:])
                    except Exception:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    audio_data = ((choices[0].get("delta") or {}).get("audio") or {}).get("data")
                    if audio_data:
                        chunks.append(audio_data)

        if not chunks:
            raise ValueError("OpenRouter TTS returned no audio data")

        return base64.b64decode("".join(chunks)), _FORMAT_TO_MIME.get(fmt, "audio/mpeg")

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        base_url = self._resolve_base_url(data) or "https://openrouter.ai/api/v1"

        extra_headers = {}
        if data:
            if data.get("httpReferer"):
                extra_headers["HTTP-Referer"] = data["httpReferer"]
            if data.get("xTitle"):
                extra_headers["X-Title"] = data["xTitle"]

        return await self._validate_openai_compatible(api_key, base_url, data, extra_headers=extra_headers)
