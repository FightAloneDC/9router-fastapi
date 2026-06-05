"""Black Forest Labs provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class BflConfig(BaseProviderConfig):
    """Black Forest Labs provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Black Forest Labs"
    PROVIDER_ID: str = "bfl"
    ALIAS: str = "bfl"
    BASE_URL: str = "https://api.bfl.ml"
    SERVICE_KINDS: list[str] = ["image"]


class BflMetadata(BaseMetadata):
    """Black Forest Labs UI display metadata."""

    name: str = "Black Forest Labs"
    color: str = "#1E40AF"
    textIcon: str = "BF"
