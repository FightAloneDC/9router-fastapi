"""Google TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GoogleTtsConfig(BaseProviderConfig):
    """Google TTS provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Google TTS"
    PROVIDER_ID: str = "google-tts"
    ALIAS: str = "gtts"
    BASE_URL: str = "https://texttospeech.googleapis.com/v1"
    SERVICE_KINDS: list[str] = ["tts"]


class GoogleTtsMetadata(BaseMetadata):
    """Google TTS UI display metadata."""

    name: str = "Google TTS"
    color: str = "#4285F4"
    textIcon: str = "GT"
    icon: str = "Volume2"
    website: str = "https://cloud.google.com/text-to-speech"
    notice: dict | None = {"apiKeyUrl": "https://console.cloud.google.com/apis/credentials"}
