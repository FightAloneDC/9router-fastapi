"""Minimax (China) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MinimaxCnConfig(BaseProviderConfig):
    """Minimax (China) provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Minimax (China)"
    PROVIDER_ID: str = "minimax-cn"
    ALIAS: str = "minimax-cn"
    BASE_URL: str = "https://api.minimax.chat/v1"
    SERVICE_KINDS: list[str] = ["llm", "tts"]


class MinimaxCnMetadata(BaseMetadata):
    """Minimax (China) UI display metadata."""

    name: str = "Minimax (China)"
    color: str = "#DC2626"
    textIcon: str = "MC"
