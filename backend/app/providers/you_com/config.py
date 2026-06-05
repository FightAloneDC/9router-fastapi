"""You.com provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class YouComConfig(BaseProviderConfig):
    """You.com provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "You.com"
    PROVIDER_ID: str = "you-com"
    ALIAS: str = "you"
    BASE_URL: str = "https://api.you.com"
    SERVICE_KINDS: list[str] = ["webSearch"]


class YouComMetadata(BaseMetadata):
    """You.com UI display metadata."""

    name: str = "You.com"
    color: str = "#8B5CF6"
    textIcon: str = "YC"
