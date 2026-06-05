"""Firecrawl provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class FirecrawlConfig(BaseProviderConfig):
    """Firecrawl provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Firecrawl"
    PROVIDER_ID: str = "firecrawl"
    ALIAS: str = "fc"
    BASE_URL: str = "https://api.firecrawl.dev"
    SERVICE_KINDS: list[str] = ["webFetch"]


class FirecrawlMetadata(BaseMetadata):
    """Firecrawl UI display metadata."""

    name: str = "Firecrawl"
    color: str = "#F97316"
    textIcon: str = "FC"
