"""OpenCode Free handler — impersonates desktop CLI client.

Adopted from the OpenCode CLI desktop app. Sends fixed headers to
masquerade as the desktop client (no user API key required).
Routes requests through the zen/v1 API path.
"""

from __future__ import annotations

import logging

from app.providers.base import BaseProviderHandler, ValidateResult

logger = logging.getLogger(__name__)


class OpencodeHandler(BaseProviderHandler):
    """Handler for OpenCode Free provider."""

    async def validate(
        self,
        api_key: str = "",
        data: dict | None = None,
    ) -> ValidateResult:
        """NoAuth provider — always valid, no key to check."""
        return ValidateResult(valid=True, latency_ms=0)

    async def fetch_models(
        self,
        api_key: str = "",
        data: dict | None = None,
    ) -> list[dict]:
        """Fetch free models from OpenCode zen endpoint.

        Filters to models ending with -free or in the known free set.
        """
        from app.providers.opencode.models import fetch_models

        return await fetch_models(api_key)

    def build_upstream_url(
        self,
        base_url: str,
        stream: bool = False,
        data: dict | None = None,
        model: str = "",
    ) -> str:
        """Route to zen/v1/chat/completions (not standard /chat/completions)."""
        return f"{base_url.rstrip('/')}/zen/v1/chat/completions"

    def build_headers(
        self,
        api_key: str = "",
        stream: bool = False,
        data: dict | None = None,
    ) -> dict[str, str]:
        """Impersonate OpenCode desktop CLI client."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": "Bearer public",
            "x-opencode-client": "desktop",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers
