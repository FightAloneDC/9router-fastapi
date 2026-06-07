"""AssemblyAI handler — raw API key + transcript endpoint."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class AssemblyaiHandler(BaseProviderHandler):
    """Handler for AssemblyAI provider."""

    async def execute_stt(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model: str,
        file_bytes: bytes,
        content_type: str,
        language: str | None = None,
        max_poll_seconds: int = 120,
        poll_interval: float = 2.0,
        **_kwargs,
    ) -> dict[str, Any]:
        """AssemblyAI STT — 3-step async flow (upload → submit → poll)."""
        if not api_key:
            raise ValueError("AssemblyAI requires an API key")

        base_url = self._resolve_base_url(None)
        headers = {"Authorization": api_key}  # AssemblyAI uses raw key, NO "Bearer " prefix

        # Step 1: Upload
        upload_resp = await client.post(
            f"{base_url}/upload",
            content=file_bytes,
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        upload_resp.raise_for_status()
        upload_url = upload_resp.json().get("upload_url")
        if not upload_url:
            raise ValueError("AssemblyAI upload returned no upload_url")

        # Step 2: Submit transcription job
        submit_body: dict[str, Any] = {"audio_url": upload_url}
        if model:
            submit_body["speech_models"] = [model]
        if language:
            submit_body["language_code"] = language
        else:
            submit_body["language_detection"] = True

        submit_resp = await client.post(
            f"{base_url}/transcript",
            json=submit_body,
            headers={**headers, "Content-Type": "application/json"},
        )
        submit_resp.raise_for_status()
        transcript_id = submit_resp.json().get("id")
        if not transcript_id:
            raise ValueError("AssemblyAI submit returned no transcript id")

        # Step 3: Poll
        poll_url = f"{base_url}/transcript/{transcript_id}"
        max_iters = max(1, int(max_poll_seconds / poll_interval))
        for _ in range(max_iters):
            await asyncio.sleep(poll_interval)
            poll_resp = await client.get(poll_url, headers=headers)
            if poll_resp.status_code != 200:
                continue
            result = poll_resp.json()
            st = result.get("status")
            if st == "completed":
                out: dict[str, Any] = {"text": result.get("text", "")}
                lang = result.get("language_code")
                if lang:
                    out["language"] = lang
                return out
            if st == "error":
                raise ValueError(
                    f"AssemblyAI transcription failed: {result.get('error', 'unknown error')}"
                )

        raise ValueError(f"AssemblyAI transcription timeout after {max_poll_seconds}s")

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for AssemblyAI")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/transcript?limit=1"
        headers = {self.config.AUTH_HEADER: api_key}

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    return ValidateResult(valid=False, error=f"AssemblyAI returned {resp.status_code}: {resp.text[:200]}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to AssemblyAI API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
