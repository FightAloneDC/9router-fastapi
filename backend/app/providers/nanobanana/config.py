"""Nanobanana provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class NanobananaConfig(BaseProviderConfig):
    """Nanobanana provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Nanobanana"
    PROVIDER_ID: str = "nanobanana"
    ALIAS: str = "nana"
    BASE_URL: str = "https://api.nanobananaapi.ai/v1"
    SERVICE_KINDS: list[str] = ["image"]


class NanobananaMetadata(BaseMetadata):
    """Nanobanana UI display metadata."""

    name: str = "Nanobanana"
    color: str = "#F59E0B"
    textIcon: str = "NB"
