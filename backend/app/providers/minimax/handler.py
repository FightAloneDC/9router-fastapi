"""Minimax handler — /get_voice endpoint."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class MinimaxHandler(BaseProviderHandler):
    """Handler for Minimax provider."""

    ENDPOINT = "https://api.minimax.io/v1/get_voice"

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for MiniMax")

        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15.0) as client:
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
