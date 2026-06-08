"""Hyperbolic provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class HyperbolicConfig(BaseProviderConfig):
    """Hyperbolic provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Hyperbolic"
    PROVIDER_ID: str = "hyperbolic"
    ALIAS: str = "hyp"
    BASE_URL: str = "https://api.hyperbolic.xyz/v1"
    SERVICE_KINDS: list[str] = ["tts"]


class HyperbolicMetadata(BaseMetadata):
    """Hyperbolic UI display metadata."""

    name: str = "Hyperbolic"
    color: str = "#8B5CF6"
    textIcon: str = "HY"
    icon: str = "Zap"
    website: str = "https://hyperbolic.xyz"
    notice: dict | None = {"apiKeyUrl": "https://app.hyperbolic.xyz/settings"}
