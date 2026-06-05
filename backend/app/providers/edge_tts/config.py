"""Edge TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class EdgeTtsConfig(BaseProviderConfig):
    """Edge TTS provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Edge TTS"
    PROVIDER_ID: str = "edge-tts"
    ALIAS: str = "edge"
    BASE_URL: str = "https://speech.platform.bing.com"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""


class EdgeTtsMetadata(BaseMetadata):
    """Edge TTS UI display metadata."""

    name: str = "Edge TTS"
    color: str = "#0078D4"
    textIcon: str = "ET"
