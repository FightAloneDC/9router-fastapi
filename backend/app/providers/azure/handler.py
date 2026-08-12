"""Azure OpenAI provider handler — api-key header + deployment URL."""

from __future__ import annotations

import io
import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class AzureHandler(BaseProviderHandler):
    """Handler for Azure OpenAI provider."""

    def _resolve_base_url(self, data: dict | None = None) -> str:
        """Azure uses azureEndpoint from providerSpecificData."""
        if data:
            endpoint = data.get("azureEndpoint") or data.get("endpoint") or ""
            if endpoint:
                return endpoint.rstrip("/")
        return super()._resolve_base_url(data)

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="No API key configured")

        data = data or {}
        endpoint = (data.get("azureEndpoint") or data.get("endpoint") or "").rstrip("/")
        deployment = data.get("deployment") or ""
        api_version = data.get("apiVersion") or "2024-02-15-preview"

        if not endpoint:
            return ValidateResult(valid=False, error="Azure endpoint URL is required")
        if not deployment:
            return ValidateResult(valid=False, error="Azure deployment name is required")

        start = time.monotonic()
        url = f"{endpoint}/openai/deployments?api-version={api_version}"
        headers = {"api-key": api_key}

        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"Azure returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error=f"Cannot connect to {endpoint}", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Azure uses deployments format with api-version."""
        data = data or {}
        endpoint = data.get("azureEndpoint") or base_url
        deployment = data.get("deployment", "gpt-4")
        api_version = data.get("apiVersion", "2024-10-01-preview")
        return f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    def build_stt_request(self, data: dict, model: str) -> tuple[str, dict[str, str]]:
        """Build STT URL and headers for Azure deployment.

        Returns:
            (url, headers) for the Azure STT endpoint.
        """
        endpoint = data.get("azureEndpoint") or self.config.BASE_URL
        deployment = data.get("deployment", "whisper")
        api_version = data.get("apiVersion", "2024-06-01")
        url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
            f"/audio/transcriptions?api-version={api_version}"
        )
        headers = {"api-key": data.get("apiKey", "")}
        return url, headers

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
        data: dict | None = None,
        **_kwargs,
    ) -> dict[str, Any]:
        """Azure Whisper-compatible multipart transcription via deployment URL."""
        if not model:
            raise ValueError("STT model is required")

        conn_data = data or {}
        endpoint = conn_data.get("azureEndpoint") or self.config.BASE_URL
        deployment = conn_data.get("deployment", "whisper")
        api_version = conn_data.get("apiVersion", "2024-06-01")
        url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
            f"/audio/transcriptions?api-version={api_version}"
        )
        headers = {"api-key": api_key}

        files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
        form_data: dict[str, str] = {"model": model}
        if language:
            form_data["language"] = language
        if prompt:
            form_data["prompt"] = prompt
        if response_format:
            form_data["response_format"] = response_format
        if temperature is not None:
            form_data["temperature"] = str(temperature)

        resp = await client.post(url, headers=headers, files=files, data=form_data)
        resp.raise_for_status()

        if response_format in ("text", "srt", "vtt"):
            return {"text": resp.text}

        return resp.json()
