"""Kilo Gateway provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class KiloGatewayConfig(BaseProviderConfig):
    """Kilo Gateway provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Kilo Gateway"
    PROVIDER_ID: str = "kilo-gateway"
    ALIAS: str = "kilo"
    BASE_URL: str = "https://api.kilo.ai/api/gateway"
    SERVICE_KINDS: list[str] = ["llm"]


class KiloGatewayMetadata(BaseMetadata):
    """Kilo Gateway UI display metadata."""

    name: str = "Kilo Gateway"
    color: str = "#FF6B35"
    textIcon: str = "KG"
    icon: str = "Code"
    website: str = "https://kilo.ai"
    notice: dict | None = {"apiKeyUrl": "https://kilo.ai"}
