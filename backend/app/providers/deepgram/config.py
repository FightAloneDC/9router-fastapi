"""Deepgram provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class DeepgramConfig(BaseProviderConfig):
    """Deepgram provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Deepgram"
    PROVIDER_ID: str = "deepgram"
    ALIAS: str = "dg"
    BASE_URL: str = "https://api.deepgram.com/v1"
    SERVICE_KINDS: list[str] = ["tts", "stt"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Token "

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "nova-3": "stt",
        "nova-2": "stt",
        "universal-3-pro": "stt",
        "universal-2": "stt",
    }


class DeepgramMetadata(BaseMetadata):
    """Deepgram UI display metadata."""

    name: str = "Deepgram"
    color: str = "#13EF93"
    textIcon: str = "DG"
    icon: str = "Mic"
    website: str = "https://deepgram.com"
    notice: dict | None = {"apiKeyUrl": "https://console.deepgram.com/product/api-keys"}
