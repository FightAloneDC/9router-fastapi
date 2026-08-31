"""Edge TTS handler — no authentication required."""

from __future__ import annotations

from typing import Any

import edge_tts
import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class EdgeTtsHandler(BaseProviderHandler):
    """Handler for Edge TTS provider (no auth)."""

    async def execute_tts(
        self,
        _client: httpx.AsyncClient,
        *,
        voice: str,
        input_text: str,
        response_format: str = "mp3",
        **_kwargs,
    ) -> tuple[bytes, str]:
        """Microsoft Edge TTS — free, no API key required."""
        if not voice:
            raise ValueError("Edge TTS requires a voice")

        communicate = edge_tts.Communicate(input_text, voice)
        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        audio = b"".join(audio_chunks)
        if not audio:
            raise ValueError("Edge TTS returned empty audio")
        return audio, "audio/mpeg"

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Fetch Microsoft Edge TTS voices (no auth required)."""
        resp = await client.get(
            "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/"
            "voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4",
        )
        resp.raise_for_status()
        payload = resp.json()

        voices: list[dict[str, Any]] = []
        items = payload if isinstance(payload, list) else payload.get("voices", [])
        for v in items:
            locale = v.get("Locale", "")
            lang = locale.split("-")[0] if locale else "en"
            friendly = v.get("FriendlyName", v.get("ShortName", ""))
            name = friendly.replace("Microsoft ", "").replace(
                " Online (Natural) - ", " ("
            )
            voices.append({
                "id": v.get("ShortName", ""),
                "name": name,
                "lang": lang,
                "gender": (v.get("Gender", "") or "").lower(),
            })
        return voices

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        return ValidateResult(valid=True, models=None)
