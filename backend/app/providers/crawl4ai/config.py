"""Crawl4AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class Crawl4aiConfig(BaseProviderConfig):
    """Crawl4AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Crawl4AI"
    PROVIDER_ID: str = "crawl4ai"
    ALIAS: str = "c4ai"
    BASE_URL: str = "https://api.crawl4ai.com"
    SERVICE_KINDS: list[str] = ["webFetch"]


class Crawl4aiMetadata(BaseMetadata):
    """Crawl4AI UI display metadata."""

    name: str = "Crawl4AI"
    color: str = "#06B6D4"
    textIcon: str = "C4"
