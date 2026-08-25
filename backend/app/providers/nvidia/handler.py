"""NVIDIA NIM handler — Bearer auth + STT endpoint."""

from __future__ import annotations

import io
import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client

# Asymmetric NIM embedders require input_type (query|passage).
# Docs: docs.api.nvidia.com/nim/reference/nvidia-llama-nemotron-embed-vl-1b-v2-infer
_ASYMMETRIC_EMBED_MARKERS = (
    "embed-vl",
    "nv-embedqa",
    "nemoretriever",
    "embed-qa",
)

# Native-only size; reduced dims rejected with
# "dimensions must be one of 2048".
# Docs: docs.nvidia.com/nim/nemo-retriever/text-embedding/2.3/reference.html
_NATIVE_ONLY_DIMS: tuple[tuple[str, int], ...] = (
    ("nemotron-3-embed", 2048),
)


def _needs_input_type(model: str) -> bool:
    mid = (model or "").lower()
    return any(m in mid for m in _ASYMMETRIC_EMBED_MARKERS)


def _native_only_dim(model: str) -> int | None:
    mid = (model or "").lower()
    for marker, dim in _NATIVE_ONLY_DIMS:
        if marker in mid:
            return dim
    return None


class NvidiaHandler(BaseProviderHandler):
    """Handler for NVIDIA NIM provider."""

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Map OpenAI-compat embeddings body for NVIDIA NIM.

        - Asymmetric models (e.g. llama-nemotron-embed-vl-*): inject
          ``input_type=query`` when the client omits it (playground /
          OpenAI SDKs do not send it).
        - ``nemotron-3-embed-*``: drop ``dimensions`` unless it is the
          native 2048 (reduced sizes are not supported).
        """
        out: dict = {**body, "model": model}
        if not out.get("input_type") and _needs_input_type(model):
            out["input_type"] = "query"
        native = _native_only_dim(model)
        dims = out.get("dimensions")
        if (
            native is not None
            and dims is not None
            and dims != native
        ):
            out.pop("dimensions", None)
        return out

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
        """NVIDIA NIM TTS — POST {base_url}/audio/speech."""
        if not voice:
            raise ValueError("NVIDIA TTS requires a voice")
        base_url = self._resolve_base_url(None)
        url = f"{base_url}/audio/speech"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body: dict = {"input": {"text": input_text}, "voice": voice}
        if tts_model:
            body["model"] = tts_model
        resp = await client.post(url, json=body, headers=headers)
        if not resp.is_success:
            raise ValueError(f"NVIDIA TTS failed: {resp.status_code} — {resp.text[:300]}")
        if not resp.content:
            raise ValueError("NVIDIA TTS returned empty audio")
        content_type = resp.headers.get("content-type") or "audio/wav"
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
        **_kwargs,
    ) -> dict[str, Any]:
        """NVIDIA NIM STT — multipart form data."""
        if not model:
            raise ValueError("NVIDIA STT requires a model")
        if not api_key:
            raise ValueError("NVIDIA STT requires an API key")

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/audio/transcriptions"

        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
        data: dict[str, str] = {"model": model}
        if language:
            data["language"] = language

        resp = await client.post(url, headers=headers, files=files, data=data)
        resp.raise_for_status()

        result = resp.json()
        return {"text": result.get("text") or result.get("transcript", "")}

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for NVIDIA")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        start = time.monotonic()
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"NVIDIA returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to NVIDIA API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
