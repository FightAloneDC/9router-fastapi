"""Cerebras provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CerebrasConfig(BaseProviderConfig):
    """Cerebras provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cerebras"
    PROVIDER_ID: str = "cerebras"
    ALIAS: str = "cb"
    BASE_URL: str = "https://api.cerebras.ai/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class CerebrasMetadata(BaseMetadata):
    """Cerebras UI display metadata."""

    name: str = "Cerebras"
    color: str = "#FF6B00"
    textIcon: str = "CB"
