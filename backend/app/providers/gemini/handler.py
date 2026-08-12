"""Gemini provider handler — query param auth (?key=)."""

from __future__ import annotations

import base64
import re
import struct
import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client

# Gemini has no voice list API — 30 prebuilt voices documented by Google.
_GEMINI_VOICES: list[dict[str, str]] = [
    {"id": "Zephyr", "name": "Zephyr", "lang": "en", "gender": "Female"},
    {"id": "Puck", "name": "Puck", "lang": "en", "gender": "Male"},
    {"id": "Charon", "name": "Charon", "lang": "en", "gender": "Male"},
    {"id": "Kore", "name": "Kore", "lang": "en", "gender": "Female"},
    {"id": "Fenrir", "name": "Fenrir", "lang": "en", "gender": "Male"},
    {"id": "Leda", "name": "Leda", "lang": "en", "gender": "Female"},
    {"id": "Orus", "name": "Orus", "lang": "en", "gender": "Male"},
    {"id": "Aoede", "name": "Aoede", "lang": "en", "gender": "Female"},
    {"id": "Callirrhoe", "name": "Callirrhoe", "lang": "en", "gender": "Female"},
    {"id": "Autonoe", "name": "Autonoe", "lang": "en", "gender": "Female"},
    {"id": "Enceladus", "name": "Enceladus", "lang": "en", "gender": "Male"},
    {"id": "Iapetus", "name": "Iapetus", "lang": "en", "gender": "Male"},
    {"id": "Umbriel", "name": "Umbriel", "lang": "en", "gender": "Male"},
    {"id": "Algieba", "name": "Algieba", "lang": "en", "gender": "Male"},
    {"id": "Despina", "name": "Despina", "lang": "en", "gender": "Female"},
    {"id": "Erinome", "name": "Erinome", "lang": "en", "gender": "Female"},
    {"id": "Algenib", "name": "Algenib", "lang": "en", "gender": "Male"},
    {"id": "Rasalgethi", "name": "Rasalgethi", "lang": "en", "gender": "Male"},
    {"id": "Laomedeia", "name": "Laomedeia", "lang": "en", "gender": "Female"},
    {"id": "Achernar", "name": "Achernar", "lang": "en", "gender": "Female"},
    {"id": "Alnilam", "name": "Alnilam", "lang": "en", "gender": "Male"},
    {"id": "Schedar", "name": "Schedar", "lang": "en", "gender": "Male"},
    {"id": "Gacrux", "name": "Gacrux", "lang": "en", "gender": "Female"},
    {"id": "Pulcherrima", "name": "Pulcherrima", "lang": "en", "gender": "Female"},
    {"id": "Achird", "name": "Achird", "lang": "en", "gender": "Male"},
    {"id": "Zubenelgenubi", "name": "Zubenelgenubi", "lang": "en", "gender": "Male"},
    {"id": "Vindemiatrix", "name": "Vindemiatrix", "lang": "en", "gender": "Female"},
    {"id": "Sadachbia", "name": "Sadachbia", "lang": "en", "gender": "Male"},
    {"id": "Sadaltager", "name": "Sadaltager", "lang": "en", "gender": "Male"},
    {"id": "Sulafat", "name": "Sulafat", "lang": "en", "gender": "Female"},
]


class GeminiHandler(BaseProviderHandler):
    """Handler for Gemini/Google provider (query param auth)."""

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Return hardcoded Gemini TTS voices (no list API available)."""
        return [dict(v) for v in _GEMINI_VOICES]

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        start = time.monotonic()
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Google returned {resp.status_code}", latency_ms=latency)
                data_resp = resp.json()
                models = []
                if isinstance(data_resp, dict) and "models" in data_resp:
                    models = [m.get("name", "").replace("models/", "") for m in data_resp["models"] if m.get("name")]
                return ValidateResult(valid=True, models=models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Google API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        voice: str,
        input_text: str,
        language: str | None = None,
        **_kwargs,
    ) -> tuple[bytes, str]:
        """Gemini TTS — generateContent with AUDIO modality. Returns WAV."""
        base_url = self._resolve_base_url(None)
        url = f"{base_url}/models/{tts_model}:generateContent?key={api_key}"

        prompt = input_text
        if not re.search(r":\s", input_text):
            prompt = f"Say in {language}: {input_text}" if language else f"Say: {input_text}"

        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                },
            },
        }
        resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
        if not resp.is_success:
            try:
                err = resp.json()
                msg = err.get("error", {}).get("message", "")
            except Exception:
                msg = ""
            raise ValueError(msg or f"Gemini TTS failed: {resp.status_code}")

        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            block = data.get("promptFeedback", {}).get("blockReason", "unknown")
            raise ValueError(f"Gemini TTS returned no candidates (blockReason: {block})")

        parts = candidates[0].get("content", {}).get("parts") or []
        b64 = None
        for p in parts:
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                b64 = inline["data"]
                break

        if not b64:
            finish = candidates[0].get("finishReason", "unknown")
            raise ValueError(f"Gemini TTS returned no audio (finishReason: {finish})")

        pcm = base64.b64decode(b64)
        wav = self._pcm_to_wav(pcm)
        return wav, "audio/wav"

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
        """Wrap raw PCM in WAV header."""
        byte_rate = sample_rate * channels * bits // 8
        block_align = channels * bits // 8
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + len(pcm_data), b"WAVE", b"fmt ",
            16, 1, channels, sample_rate, byte_rate, block_align, bits,
            b"data", len(pcm_data),
        )
        return header + pcm_data

    async def execute_stt(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model: str,
        file_bytes: bytes,
        content_type: str,
        language: str | None = None,
        prompt: str | None = None,
        **_kwargs,
    ) -> dict[str, Any]:
        """Gemini STT — generateContent with audio as base64 inline_data."""
        if not model:
            raise ValueError("Gemini STT requires a model")
        if not api_key:
            raise ValueError("Gemini requires an API key")

        b64_audio = base64.b64encode(file_bytes).decode("ascii")

        instruction = prompt or (
            "Generate a transcript of the speech. "
            "Return only the transcribed text, no commentary."
        )
        if language:
            instruction += f" Language: {language}."

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": instruction},
                        {"inline_data": {"mime_type": content_type, "data": b64_audio}},
                    ]
                }
            ]
        }

        resp = await client.post(url, json=body)
        resp.raise_for_status()

        data = resp.json()
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(p.get("text", "") for p in parts if "text" in p)
        return {"text": text.strip()}

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        from app.providers.model_helpers import fetch_models_query_auth
        from app.providers.base import BaseProviderConfig

        if not api_key:
            raise ValueError("No API key configured")

        config = BaseProviderConfig(
            PROVIDER_NAME="Gemini",
            PROVIDER_ID="gemini",
            ALIAS="gemini",
            BASE_URL="https://generativelanguage.googleapis.com/v1beta",
            AUTH_QUERY_PARAM="key",
        )
        models_raw = await fetch_models_query_auth(config, api_key)

        normalized = []
        for m in models_raw:
            name = m.get("name", "").replace("models/", "")
            if name:
                normalized.append({"id": name, "name": name})
        return [self._normalize_model(m) for m in normalized if self._normalize_model(m).get("id")]

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Gemini uses /models/{model}:generateContent format."""
        base = base_url.rstrip("/")
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_id = model.replace("models/", "") if model else ""
        if model_id:
            return f"{base}/models/{model_id}:{action}"
        return f"{base}/models"

    def build_embeddings_url(self, chat_url: str) -> str:
        """Gemini uses embedContent instead of /embeddings."""
        if ":generateContent" in chat_url:
            return chat_url.replace(":generateContent", ":embedContent")
        return super().build_embeddings_url(chat_url)

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Gemini uses content.parts format for embeddings."""
        input_text = body.get("input", "")
        if isinstance(input_text, list):
            input_text = " ".join(str(x) for x in input_text)
        return {
            "model": model,
            "content": {"parts": [{"text": str(input_text)}]},
        }
