"""Topaz provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class TopazConfig(BaseProviderConfig):
    """Topaz provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Topaz"
    PROVIDER_ID: str = "topaz"
    ALIAS: str = "topaz"
    BASE_URL: str = "https://api.topazlabs.com"
    SERVICE_KINDS: list[str] = ["image"]


class TopazMetadata(BaseMetadata):
    """Topaz UI display metadata."""

    name: str = "Topaz"
    color: str = "#059669"
    textIcon: str = "TP"
