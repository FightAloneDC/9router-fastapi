"""Minimax handler — /get_voice endpoint."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


_FORMAT_TO_MIME: dict[str, str] = {
    "mp3": "audio/mpeg", "wav": "audio/wav", "opus": "audio/opus",
    "aac": "audio/aac", "flac": "audio/flac", "pcm": "audio/L16",
}


class MinimaxHandler(BaseProviderHandler):
    """Handler for Minimax provider."""

    ENDPOINT = "https://api.minimax.io/v1/get_voice"

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        response_format: str = "mp3",
        **_kwargs,
    ) -> tuple[bytes, str]:
        """MiniMax T2A HTTP — hex-encoded audio in JSON response."""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": tts_model, "text": input_text, "stream": False,
            "language_boost": "auto", "output_format": "hex",
            "voice_setting": {"voice_id": voice, "speed": 1, "vol": 1, "pitch": 0},
            "audio_setting": {
                "sample_rate": 32000, "bitrate": 128000,
                "format": response_format if response_format in {"mp3", "wav", "pcm", "flac"} else "mp3",
                "channel": 1,
            },
        }
        resp = await client.post(base_url, json=body, headers=headers)

        raw = resp.text
        data: dict = {}
        if raw:
            try:
                data = resp.json()
            except Exception:
                data = {}

        base_resp = data.get("base_resp") or data.get("baseResp") or {}
        status_code = int(base_resp.get("status_code", base_resp.get("statusCode", 0)) or 0)
        status_msg = base_resp.get("status_msg") or base_resp.get("statusMsg") or data.get("message") or ""

        if not resp.is_success:
            raise ValueError(status_msg or raw[:300] or f"MiniMax TTS error ({resp.status_code})")
        if status_code != 0:
            raise ValueError(status_msg or "MiniMax TTS upstream error")

        audio_hex = (data.get("data") or {}).get("audio") or ""
        if not audio_hex:
            raise ValueError("MiniMax TTS returned no audio")

        audio_hex = audio_hex.strip()
        if len(audio_hex) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in audio_hex):
            raise ValueError("MiniMax TTS returned invalid hex audio")

        audio_bytes = bytes.fromhex(audio_hex)
        fmt = (data.get("extra_info") or data.get("extraInfo") or {}).get("audio_format") or "mp3"
        return audio_bytes, _FORMAT_TO_MIME.get(fmt, "audio/mpeg")

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Fetch MiniMax voices via POST /v1/get_voice."""
        if not api_key:
            raise ValueError("MiniMax requires an API key")

        resp = await client.post(
            self.ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"voice_type": "all"},
        )
        resp.raise_for_status()
        data = resp.json()

        # MiniMax error envelope
        base_resp = data.get("base_resp") or data.get("baseResp") or {}
        status_code = (
            base_resp.get("status_code")
            if base_resp.get("status_code") is not None
            else base_resp.get("statusCode", 0)
        )
        if status_code != 0:
            raise Exception(
                base_resp.get("status_msg")
                or base_resp.get("statusMsg")
                or "MiniMax error"
            )

        voices: list[dict[str, Any]] = []
        for group_key, group_label in [
            ("system_voice", "System"),
            ("voice_cloning", "Cloned"),
            ("voice_generation", "Generated"),
        ]:
            for item in data.get(group_key, []) or []:
                voice_id = item.get("voice_id") or item.get("voiceId", "")
                voice_name = (
                    item.get("voice_name")
                    or item.get("voiceName")
                    or voice_id
                )
                lang = "Custom"
                if group_key == "system_voice" and "_" in voice_id:
                    lang = voice_id.split("_")[0]
                voices.append({
                    "id": voice_id,
                    "name": (
                        f"{voice_name} · {group_label}"
                        if group_key != "system_voice"
                        else voice_name
                    ),
                    "lang": lang,
                    "gender": "",
                })
        return voices

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for MiniMax")

        start = time.monotonic()
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.post(
                    self.ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"voice_type": "all"},
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"MiniMax returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                resp_data = resp.json()
                base_resp = resp_data.get("base_resp") or resp_data.get("baseResp", {})
                status_code = base_resp.get("status_code") or base_resp.get("statusCode", 0)
                if status_code != 0:
                    return ValidateResult(valid=False, error=base_resp.get("status_msg") or base_resp.get("statusMsg", "MiniMax error"), latency_ms=latency)
                voices = resp_data.get("system_voice", []) or []
                voice_ids = [v.get("voice_id") or v.get("voiceId", "") for v in voices if v.get("voice_id") or v.get("voiceId")]
                return ValidateResult(valid=True, models=voice_ids or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to MiniMax API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
