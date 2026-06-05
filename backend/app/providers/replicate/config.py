"""Replicate provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ReplicateConfig(BaseProviderConfig):
    """Replicate provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Replicate"
    PROVIDER_ID: str = "replicate"
    ALIAS: str = "rep"
    BASE_URL: str = "https://api.replicate.com/v1"
    SERVICE_KINDS: list[str] = ["image"]


class ReplicateMetadata(BaseMetadata):
    """Replicate UI display metadata."""

    name: str = "Replicate"
    color: str = "#000000"
    textIcon: str = "RP"
