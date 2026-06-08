"""Tavily provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class TavilyConfig(BaseProviderConfig):
    """Tavily provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Tavily"
    PROVIDER_ID: str = "tavily"
    ALIAS: str = "tavily"
    BASE_URL: str = "https://api.tavily.com"
    SERVICE_KINDS: list[str] = ["webSearch", "webFetch"]


class TavilyMetadata(BaseMetadata):
    """Tavily UI display metadata."""

    name: str = "Tavily"
    color: str = "#5B21B6"
    textIcon: str = "TV"
    icon: str = "Search"
    website: str = "https://tavily.com"
    notice: dict | None = {"apiKeyUrl": "https://app.tavily.com/home"}
