"""Cartesia provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CartesiaConfig(BaseProviderConfig):
    """Cartesia provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cartesia"
    PROVIDER_ID: str = "cartesia"
    ALIAS: str = "cart"
    BASE_URL: str = "https://api.cartesia.ai"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = "X-API-Key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {"Cartesia-Version": "2024-06-10"}


class CartesiaMetadata(BaseMetadata):
    """Cartesia UI display metadata."""

    name: str = "Cartesia"
    color: str = "#06B6D4"
    textIcon: str = "CA"
    icon: str = "AudioLines"
    website: str = "https://cartesia.ai"
    notice: dict | None = {"apiKeyUrl": "https://play.cartesia.ai/keys"}
