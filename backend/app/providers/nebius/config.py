"""Nebius AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class NebiusConfig(BaseProviderConfig):
    """Nebius AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Nebius AI"
    PROVIDER_ID: str = "nebius"
    ALIAS: str = "nb"
    BASE_URL: str = "https://api.studio.nebius.ai/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]


class NebiusMetadata(BaseMetadata):
    """Nebius AI UI display metadata."""

    name: str = "Nebius AI"
    color: str = "#00A3FF"
    textIcon: str = "NB"
    icon: str = "Cloud"
    website: str = "https://nebius.ai"
    notice: dict | None = {"apiKeyUrl": "https://studio.nebius.ai/settings/api-keys"}
