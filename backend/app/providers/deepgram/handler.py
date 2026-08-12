"""Deepgram handler — Token auth + custom model list."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class DeepgramHandler(BaseProviderHandler):
    """Handler for Deepgram provider."""

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
        """Deepgram TTS — POST {base_url}/speak?model={voice}, Token auth."""
        upstream_model = voice or tts_model
        if not upstream_model:
            raise ValueError("Deepgram TTS requires a voice/model")

        base_url = self._resolve_base_url(None)
        url = f"{base_url}/speak?model={upstream_model}"
        headers = {
            self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}",
            "Content-Type": "application/json",
        }
        resp = await client.post(url, json={"text": input_text}, headers=headers)
        if not resp.is_success:
            raise ValueError(f"Deepgram TTS failed: {resp.status_code} — {resp.text[:300]}")
        if not resp.content:
            raise ValueError("Deepgram TTS returned empty audio")
        content_type = resp.headers.get("content-type") or "audio/mpeg"
        return resp.content, content_type

    async def execute_stt(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model: str,
        file_bytes: bytes,
        content_type: str,
        language: str | None = None,
        **_kwargs,
    ) -> dict[str, Any]:
        """Deepgram STT — raw binary POST with model as query param.

        Uses ``Token`` auth prefix (NOT Bearer).
        """
        if not model:
            raise ValueError("Deepgram requires a model (e.g. 'nova-3')")
        if not api_key:
            raise ValueError("Deepgram requires an API key")

        base_url = self._resolve_base_url(None)
        params = [f"model={model}", "smart_format=true", "punctuate=true"]
        if language:
            params.append(f"language={language}")
        else:
            params.append("detect_language=true")
        url = f"{base_url}?{'&'.join(params)}"

        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        }

        resp = await client.post(url, content=file_bytes, headers=headers)
        resp.raise_for_status()

        data = resp.json()
        transcript = (
            data.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
        )
        detected_lang = data.get("results", {}).get("channels", [{}])[0].get("detected_language")
        out: dict[str, Any] = {"text": transcript}
        if detected_lang:
            out["language"] = detected_lang
        return out

    async def fetch_voices(self, client: httpx.AsyncClient, api_key: str = "") -> list[dict[str, Any]]:
        """Fetch Deepgram TTS models (each model = one voice)."""
        if not api_key:
            raise ValueError("Deepgram requires an API key")
        base_url = self.config.BASE_URL.rstrip("/")
        resp = await client.get(
            f"{base_url}/models",
            headers={self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

        voices: list[dict[str, Any]] = []
        for m in data.get("tts", []) or []:
            langs = m.get("languages", ["en"]) or ["en"]
            voice_id = m.get("canonical_name") or m.get("name", "")
            gender = ""
            for tag in (m.get("metadata") or {}).get("tags", []) or []:
                if tag in ("masculine", "feminine"):
                    gender = tag
                    break
            for lang in langs:
                voices.append({
                    "id": voice_id,
                    "name": m.get("name", voice_id),
                    "lang": lang,
                    "gender": gender,
                })
        return voices

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Deepgram")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/models"
        headers = {self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}"}

        start = time.monotonic()
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Deepgram returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                data_resp = resp.json()
                tts_models = [m.get("canonical_name") or m.get("name", "") for m in data_resp.get("tts", []) if m.get("name")]
                stt_models = [m.get("canonical_name") or m.get("name", "") for m in data_resp.get("stt", []) if m.get("name")]
                all_models = tts_models + stt_models
                return ValidateResult(valid=True, models=all_models or None, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Deepgram API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
