"""Recraft provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class RecraftConfig(BaseProviderConfig):
    """Recraft provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Recraft"
    PROVIDER_ID: str = "recraft"
    ALIAS: str = "recraft"
    BASE_URL: str = "https://external.api.recraft.ai/v1"
    SERVICE_KINDS: list[str] = ["image"]


class RecraftMetadata(BaseMetadata):
    """Recraft UI display metadata."""

    name: str = "Recraft"
    color: str = "#EC4899"
    textIcon: str = "RC"
