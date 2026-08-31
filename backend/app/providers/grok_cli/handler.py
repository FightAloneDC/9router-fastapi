"""Grok CLI provider handler.

Upstream is the OpenAI Responses API on cli-chat-proxy.grok.com
(FORMAT="openai-responses"). Port of ``open-sse/executors/grok-cli.js``
header/URL/validation behavior from the Next.js reference; request body
transformation lives in ``transform.py`` (PS rule).
"""

from __future__ import annotations

import json
import time

from app.providers.base import BaseProviderHandler, ValidateResult
from app.providers.grok_cli import models as grok_models
from app.providers.grok_cli import quality_gate, transform
from app.providers.grok_cli.constants import QUALITY_GATE_407


class GrokCliHandler(BaseProviderHandler):
    """Handler for the Grok CLI (Grok Build) provider."""

    def build_upstream_url(
        self, base_url: str, stream: bool = False,
        data: dict | None = None, model: str = "",
    ) -> str:
        """Grok CLI speaks the Responses API: POST {base}/responses."""
        return f"{base_url.rstrip('/')}/responses"

    def build_headers(
        self, api_key: str, stream: bool = False,
        data: dict | None = None,
    ) -> dict[str, str]:
        """Auth + static fingerprint + identity headers.

        Chat requests replace these via build_request_body(), which adds
        the dynamic per-request headers (session/req/turn ids).
        """
        if not api_key:
            raise ValueError(
                "No Grok CLI access token configured"
            )
        headers = {"Content-Type": "application/json"}
        headers[self.config.AUTH_HEADER] = (
            f"{self.config.AUTH_PREFIX}{api_key}"
        )
        headers.update(self.config.EXTRA_HEADERS)
        if stream:
            headers["Accept"] = "text/event-stream"

        psd = (data or {}).get("providerSpecificData") or {}
        email = psd.get("email") or (data or {}).get("email")
        user_id = psd.get("userId")
        if email:
            headers["x-email"] = email
        if user_id:
            headers["x-userid"] = str(user_id)
        return headers

    async def validate(
        self, api_key: str, data: dict | None = None,
    ) -> ValidateResult:
        """Validate by fetching /models with the full CLI fingerprint."""
        if not api_key:
            return ValidateResult(valid=False, error="No token configured")

        start = time.monotonic()
        try:
            fetched = await grok_models.fetch_models(api_key, data)
            latency = int((time.monotonic() - start) * 1000)
            model_ids = [m.get("id", "") for m in fetched if m.get("id")]
            return ValidateResult(
                valid=True, models=model_ids or None, latency_ms=latency,
            )
        except Exception as e:
            latency = int((time.monotonic() - start) * 1000)
            return ValidateResult(
                valid=False, error=str(e)[:200], latency_ms=latency,
            )

    async def fetch_models(
        self, api_key: str, data: dict | None = None,
    ) -> list[dict]:
        """Fetch models from cli-chat-proxy.grok.com.

        Raises:
            httpx.HTTPStatusError: on non-2xx (e.g. 401 expired token).
        """
        fetched = await grok_models.fetch_models(api_key, data)
        return [
            self._normalize_model(m)
            for m in fetched
            if self._normalize_model(m).get("id")
        ]

    async def build_request_body(
        self, model: str, body: dict, data: dict | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """Transform the client body into a Grok CLI Responses request.

        Returns:
            (json_body_bytes, full_headers) — headers include the dynamic
            x-grok-session-id / req-id / turn-idx / agent-id fingerprint.
        """
        if not model:
            raise ValueError("Grok CLI requires a resolved model")

        access_token = (data or {}).get("accessToken", "")
        if not access_token:
            raise ValueError("No Grok CLI access token configured")

        transformed, meta = transform.build_grok_cli_request(
            model=model, body=body, data=data or {},
        )

        headers = self.build_headers(access_token, stream=True, data=data)
        headers["x-grok-session-id"] = meta["sessionId"]
        # CLI uses the same id for conv + session on chat turns
        headers["x-grok-conv-id"] = meta["sessionId"]
        headers["x-grok-req-id"] = meta["reqId"]
        headers["x-grok-turn-idx"] = str(meta["turnIdx"])
        if meta.get("agentId"):
            headers["x-grok-agent-id"] = meta["agentId"]
        headers["x-grok-model-override"] = meta["model"]
        headers["Accept"] = "text/event-stream"

        return json.dumps(transformed).encode("utf-8"), headers

    async def before_user_forward(
        self,
        *,
        url: str,
        model: str,
        conn_data: dict,
        proxy: str | None = None,
        connection_id: str | None = None,
    ) -> bool:
        """Probe this connection only; pass iff output is exactly 407."""
        if not QUALITY_GATE_407:
            return True
        return await quality_gate.probe_literal_407(
            handler=self,
            url=url,
            conn_data=conn_data,
            proxy=proxy,
            connection_id=connection_id,
        )
