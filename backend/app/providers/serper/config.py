"""Serper provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class SerperConfig(BaseProviderConfig):
    """Serper provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Serper"
    PROVIDER_ID: str = "serper"
    ALIAS: str = "serper"
    BASE_URL: str = "https://serper.dev/api"
    SERVICE_KINDS: list[str] = ["webSearch"]


class SerperMetadata(BaseMetadata):
    """Serper UI display metadata."""

    name: str = "Serper"
    color: str = "#4F46E5"
    textIcon: str = "SP"
    icon: str = "Search"
    website: str = "https://serper.dev"
    notice: dict | None = {"apiKeyUrl": "https://serper.dev/api-key"}
