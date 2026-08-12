"""Vertex AI handler — service account JSON + API key validation."""

import json
import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class VertexHandler(BaseProviderHandler):
    """Handler for Vertex AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key or service account JSON is required")

        # Service account JSON
        try:
            parsed = json.loads(api_key)
            if isinstance(parsed, dict) and parsed.get("type") == "service_account":
                valid = bool(parsed.get("client_email") and parsed.get("private_key") and parsed.get("project_id"))
                return ValidateResult(valid=valid, error=None if valid else "Invalid service account JSON")
        except (json.JSONDecodeError, TypeError):
            pass

        # Raw API key: probe Vertex
        start = time.monotonic()
        url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/__probe__:generateContent?key={api_key}"
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers={"Content-Type": "application/json"}, json={})
                latency = int((time.monotonic() - start) * 1000)
                valid = resp.status_code not in (401, 403)
                return ValidateResult(valid=valid, error=None if valid else "Invalid API key", latency_ms=latency)
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))
