"""Linkup provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class LinkupConfig(BaseProviderConfig):
    """Linkup provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Linkup"
    PROVIDER_ID: str = "linkup"
    ALIAS: str = "lk"
    BASE_URL: str = "https://api.linkup.so"
    SERVICE_KINDS: list[str] = ["webSearch"]


class LinkupMetadata(BaseMetadata):
    """Linkup UI display metadata."""

    name: str = "Linkup"
    color: str = "#3B82F6"
    textIcon: str = "LK"
    icon: str = "Search"
    website: str = "https://linkup.so"
    notice: dict | None = {"apiKeyUrl": "https://linkup.so/dashboard"}
