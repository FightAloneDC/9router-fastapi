"""HuggingFace handler — Bearer auth + model-specific URLs."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class HuggingfaceHandler(BaseProviderHandler):
    """Handler for HuggingFace Inference API."""

    async def execute_tts(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        tts_model: str,
        input_text: str,
        response_format: str = "wav",
        **_kwargs,
    ) -> tuple[bytes, str]:
        """HuggingFace TTS — POST {base_url}/models/{model}."""
        if not tts_model:
            raise ValueError("HuggingFace TTS requires a model")
        if ".." in tts_model:
            raise ValueError("Invalid HuggingFace model ID (path traversal)")
        base_url = self._resolve_base_url(None)
        url = f"{base_url}/models/{tts_model.lstrip('/')}"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = await client.post(url, json={"inputs": input_text}, headers=headers)
        if not resp.is_success:
            raise ValueError(f"HuggingFace TTS failed: {resp.status_code} — {resp.text[:300]}")
        if not resp.content:
            raise ValueError("HuggingFace TTS returned empty audio")
        content_type = resp.headers.get("content-type") or "audio/wav"
        return resp.content, content_type

    async def execute_stt(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model: str,
        file_bytes: bytes,
        content_type: str,
        **_kwargs,
    ) -> dict[str, Any]:
        """HuggingFace ASR — raw binary POST to ``{base_url}/models/{model}``."""
        if not model:
            raise ValueError("HuggingFace requires a model id")
        if ".." in model.split("/"):
            raise ValueError("Invalid HuggingFace model id (contains '..')")

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/models/{model}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
        }

        resp = await client.post(url, content=file_bytes, headers=headers)
        resp.raise_for_status()

        data = resp.json()
        if isinstance(data, dict) and "text" in data:
            return {"text": data["text"]}
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return {"text": data[0].get("text", "")}
        return {"text": str(data)}

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for HuggingFace")

        base_url = self._resolve_base_url(data)
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"HuggingFace returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to HuggingFace API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
