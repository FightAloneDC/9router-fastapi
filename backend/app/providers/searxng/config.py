"""SearXNG provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class SearxngConfig(BaseProviderConfig):
    """SearXNG provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SearXNG"
    PROVIDER_ID: str = "searxng"
    ALIAS: str = "sx"
    BASE_URL: str = "http://localhost:8080"
    SERVICE_KINDS: list[str] = ["webSearch"]


class SearxngMetadata(BaseMetadata):
    """SearXNG UI display metadata."""

    name: str = "SearXNG"
    color: str = "#FF6B35"
    textIcon: str = "SX"
    icon: str = "Search"
    website: str = "https://searxng.org"
    notice: dict | None = {"text": "Self-hosted metasearch engine."}
