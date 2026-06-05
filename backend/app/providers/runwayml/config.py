"""Runway ML provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class RunwaymlConfig(BaseProviderConfig):
    """Runway ML provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Runway ML"
    PROVIDER_ID: str = "runwayml"
    ALIAS: str = "runway"
    BASE_URL: str = "https://api.dev.runwayml.com/v1"
    SERVICE_KINDS: list[str] = ["image", "video"]


class RunwaymlMetadata(BaseMetadata):
    """Runway ML UI display metadata."""

    name: str = "Runway ML"
    color: str = "#000000"
    textIcon: str = "RW"
