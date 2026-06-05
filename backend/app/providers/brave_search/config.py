"""Brave Search provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class BraveSearchConfig(BaseProviderConfig):
    """Brave Search provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Brave Search"
    PROVIDER_ID: str = "brave-search"
    ALIAS: str = "brave"
    BASE_URL: str = "https://api.search.brave.com/res/v1"
    SERVICE_KINDS: list[str] = ["webSearch"]


class BraveSearchMetadata(BaseMetadata):
    """Brave Search UI display metadata."""

    name: str = "Brave Search"
    color: str = "#FB542B"
    textIcon: str = "BR"
