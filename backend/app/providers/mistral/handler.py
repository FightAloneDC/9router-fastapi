"""Mistral handler — drop client-only / unsupported chat extras."""

from __future__ import annotations

import json
from app.providers.base import BaseProviderHandler
from app.providers.mistral.transform import sanitize_mistral_chat_body


class MistralHandler(BaseProviderHandler):
    """OpenAI-compatible chat with a sanitized request body."""

    async def build_request_body(
        self,
        model: str,
        body: dict,
        conn_data: dict | None = None,
    ) -> tuple[bytes, dict[str, str] | None]:
        del conn_data
        sanitized = sanitize_mistral_chat_body(model, body)
        return json.dumps(sanitized).encode(), None
