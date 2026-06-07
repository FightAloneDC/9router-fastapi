"""Cloudflare AI handler — accountId + chat completion test."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult


class CloudflareAiHandler(BaseProviderHandler):
    """Handler for Cloudflare AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        data = data or {}
        account_id = data.get("accountId", "")
        if not account_id:
            return ValidateResult(valid=False, error="Cloudflare Account ID is required")
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Cloudflare AI")

        start = time.monotonic()
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "@cf/meta/llama-3-8b-instruct",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key or Account ID (unauthorized)", latency_ms=latency)
                if resp.status_code >= 400:
                    resp_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    errors = resp_data.get("errors", [])
                    msg = errors[0].get("message", f"Cloudflare returned {resp.status_code}") if errors else f"Cloudflare returned {resp.status_code}"
                    return ValidateResult(valid=False, error=msg, latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Cloudflare API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
