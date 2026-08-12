"""Qoder provider handler — COSY-signed requests, custom URL/headers/body/envelope.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/archives/qoder-docs/BUG-FIXING-LOG.md before making any changes.

Qoder is a special provider that uses:
- qodercli-style COSY headers for authentication
- WAF-bypass body encoding
- Custom request/response transformation
- OAuth device flow + PAT import for connection setup

All Qoder-specific code lives in providers/qoder/.
"""

import json
import logging
import time
from typing import Any

from app.providers.base import BaseProviderHandler, ValidateResult

logger = logging.getLogger(__name__)


class QoderHandler(BaseProviderHandler):
    """Handler for Qoder provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        """Validate Qoder credentials.

        Validate against Qoder user info rather than only checking that the
        token exists. PAT-exchanged job tokens can be present but inactive;
        Qoder then returns TOKEN_EXPIRE/Login expired during model/chat calls.
        """
        if not api_key:
            return ValidateResult(valid=False, error="No Qoder token configured")
        start = time.monotonic()
        try:
            from app.providers.qoder.auth import fetch_user_info

            await fetch_user_info(api_key)
            return ValidateResult(
                valid=True,
                models=None,
                latency_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return ValidateResult(
                valid=False,
                error=str(e)[:200],
                latency_ms=int((time.monotonic() - start) * 1000),
            )

    async def try_refresh_on_auth_error(
        self,
        db: object,
        connection_id: str,
    ) -> bool:
        """Refresh Qoder job token after 401/403 or build failure."""
        from app.providers.qoder.auth import try_refresh_connection

        return await try_refresh_connection(db, connection_id)

    def build_upstream_url(self, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
        """Qoder uses COSY-signed endpoint with Encode=1."""
        from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED
        return QODER_CHAT_URL_ENCODED

    def build_headers(self, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
        """Build COSY-signed headers for Qoder.

        The actual content signature is rebuilt in build_request_body() for
        providers using a custom raw body.
        """
        from app.providers.qoder.cosy import build_cosy_headers
        from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")

        if not user_id:
            raise ValueError("Qoder userId missing — cannot build COSY headers")

        # Build placeholder headers with empty body. The actual content
        # signature is rebuilt in build_request_body().
        cosy_headers = build_cosy_headers(
            body=b"",
            request_url=QODER_CHAT_URL_ENCODED,
            user_id=user_id,
            auth_token=api_key,
            name=data.get("displayName", ""),
            email=data.get("email", ""),
            machine_id=machine_id,
        )

        if stream:
            cosy_headers["Accept"] = "text/event-stream"

        return cosy_headers

    async def build_request_body(self, model: str, body: dict, data: dict | None = None) -> tuple[bytes, dict[str, str]]:
        """Transform OpenAI-format request to Qoder format with COSY signing.

        Returns:
            (encoded_body_bytes, signed_headers) tuple
        """
        from app.providers.qoder.transform import build_qoder_request_body
        from app.providers.qoder.cosy import build_cosy_headers
        from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED
        from app.providers.qoder.models import get_qoder_model_config, resolve_qoder_models
        from app.providers.qoder.encoding import qoder_encode_body
        from app.services.proxy import ALIAS_TO_ID

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")
        access_token = data.get("accessToken", "")

        # Resolve model ID: "qd/qoder/auto" -> "auto"
        if "/" in model:
            parts = model.split("/", 1)
            resolved = ALIAS_TO_ID.get(parts[0], parts[0])
            remainder = parts[1]
            qoder_key = remainder[len(resolved) + 1:] if remainder.startswith(resolved + "/") else remainder
        else:
            qoder_key = model

        # Get model config from cache
        model_config = get_qoder_model_config(user_id, access_token, qoder_key)

        # If not in cache, fetch from API. Qoder silently downgrades
        # when given a wrong/incomplete model_config, so this is a hard error.
        if model_config is None:
            credentials = {
                "access_token": access_token,
                "provider_specific": {"userId": user_id, "machineId": machine_id},
            }
            await resolve_qoder_models(credentials, force_refresh=True)
            model_config = get_qoder_model_config(user_id, access_token, qoder_key)
            if model_config is None:
                raise ValueError(
                    f"qoder: model_config for \"{qoder_key}\" not found. "
                    "Fetch models first or check upstream connectivity."
                )

        # Build Qoder-format request body
        qoder_body = build_qoder_request_body(
            model=model,
            body=body,
            credentials={"provider_specific": {"userId": user_id, "machineId": machine_id}},
            model_config=model_config,
            qoder_key=qoder_key,
        )

        # JSON -> WAF-bypass encode
        plain_bytes = json.dumps(qoder_body).encode("utf-8")
        encoded_str = qoder_encode_body(plain_bytes)
        encoded_bytes = encoded_str.encode("latin1")

        # Build COSY headers with the encoded body, matching qodercli-style
        # Bearer COSY authorization for /algo endpoints.
        cosy_headers = build_cosy_headers(
            body=encoded_bytes,
            request_url=QODER_CHAT_URL_ENCODED,
            user_id=user_id,
            auth_token=access_token,
            name=data.get("displayName", ""),
            email=data.get("email", ""),
            machine_id=machine_id,
        )

        return encoded_bytes, cosy_headers

    def unwrap_response(self, response_text: str) -> dict[str, Any]:
        """Unwrap Qoder's custom response envelope."""
        from app.providers.qoder.transform import unwrap_qoder_response
        return unwrap_qoder_response(response_text)

    async def fetch_models(self, api_key: str, data: dict | None = None) -> list[dict]:
        """Fetch models from Qoder catalog (COSY-signed).

        Raises:
            httpx.HTTPStatusError: If the API returns a non-200 status code (e.g. 403 for expired token)
        """
        from app.providers.qoder.models import resolve_qoder_models

        data = data or {}
        user_id = data.get("userId", "")
        machine_id = data.get("machineId", "")

        credentials = {
            "access_token": api_key,
            "provider_specific": {
                "userId": user_id,
                "machineId": machine_id,
            },
        }

        # This may raise httpx.HTTPStatusError for expired tokens
        result = await resolve_qoder_models(credentials, force_refresh=True)

        models = []
        for m in result.get("models", []):
            model_id = m.get("id", "")
            if model_id:
                models.append({
                    "id": f"qoder/{model_id}",
                    "name": m.get("name", model_id),
                    "type": "llm",
                    "contextLength": m.get("context_length", 0),
                })

        return [self._normalize_model(m) for m in models if self._normalize_model(m).get("id")]
