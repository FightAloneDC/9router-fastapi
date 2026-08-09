"""Alibaba Studio request compatibility handler."""

from __future__ import annotations

from app.providers.base import BaseProviderHandler


class AlimsIntlHandler(BaseProviderHandler):
    """Adapt OpenAI developer messages for Alibaba Studio."""

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        """Map the unsupported developer role to the supported system role."""
        messages = body.get("messages")
        if not isinstance(messages, list):
            return headers, body

        normalized_messages = [
            {
                **message,
                "role": "system"
                if isinstance(message, dict)
                and message.get("role") == "developer"
                else message.get("role"),
            }
            if isinstance(message, dict)
            else message
            for message in messages
        ]

        return {**headers}, {**body, "messages": normalized_messages}
