"""ElevenLabs provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ElevenlabsConfig(BaseProviderConfig):
    """ElevenLabs provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "ElevenLabs"
    PROVIDER_ID: str = "elevenlabs"
    ALIAS: str = "el"
    BASE_URL: str = "https://api.elevenlabs.io/v1"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = "xi-api-key"
    AUTH_PREFIX: str = ""


class ElevenlabsMetadata(BaseMetadata):
    """ElevenLabs UI display metadata."""

    name: str = "ElevenLabs"
    color: str = "#000000"
    textIcon: str = "EL"
