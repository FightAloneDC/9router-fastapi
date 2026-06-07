"""Brave Search provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class BraveConfig(BaseProviderConfig):
    """Brave Search provider configuration."""

    PROVIDER_NAME: str = "Brave Search"
    PROVIDER_ID: str = "brave-search"
    ALIAS: str = "brave"
    BASE_URL: str = "https://api.search.brave.com/res/v1"
    SERVICE_KINDS: list[str] = ["webSearch"]


class BraveMetadata(BaseMetadata):
    """Brave Search UI display metadata."""

    name: str = "Brave Search"
    color: str = "#FB5C3A"
    textIcon: str = "BR"
