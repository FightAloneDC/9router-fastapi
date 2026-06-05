"""Stability AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class StabilityAiConfig(BaseProviderConfig):
    """Stability AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Stability AI"
    PROVIDER_ID: str = "stability-ai"
    ALIAS: str = "stability"
    BASE_URL: str = "https://api.stability.ai/v2beta"
    SERVICE_KINDS: list[str] = ["image"]


class StabilityAiMetadata(BaseMetadata):
    """Stability AI UI display metadata."""

    name: str = "Stability AI"
    color: str = "#8B5CF6"
    textIcon: str = "SA"
