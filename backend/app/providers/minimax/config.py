"""Minimax Coding provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MinimaxConfig(BaseProviderConfig):
    """Minimax Coding provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Minimax Coding"
    PROVIDER_ID: str = "minimax"
    ALIAS: str = "minimax"
    BASE_URL: str = "https://api.minimax.chat/v1"
    SERVICE_KINDS: list[str] = ["llm", "image", "imageToText", "webSearch", "tts"]


class MinimaxMetadata(BaseMetadata):
    """Minimax Coding UI display metadata."""

    name: str = "Minimax Coding"
    color: str = "#7C3AED"
    textIcon: str = "MM"
