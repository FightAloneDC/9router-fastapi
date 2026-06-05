"""Exa provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ExaConfig(BaseProviderConfig):
    """Exa provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Exa"
    PROVIDER_ID: str = "exa"
    ALIAS: str = "exa"
    BASE_URL: str = "https://api.exa.ai"
    SERVICE_KINDS: list[str] = ["webSearch", "webFetch"]


class ExaMetadata(BaseMetadata):
    """Exa UI display metadata."""

    name: str = "Exa"
    color: str = "#2563EB"
    textIcon: str = "EX"
