"""Coqui TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CoquiConfig(BaseProviderConfig):
    """Coqui TTS provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Coqui TTS"
    PROVIDER_ID: str = "coqui"
    ALIAS: str = "cq"
    BASE_URL: str = "https://app.coqui.ai/api/v2"
    SERVICE_KINDS: list[str] = ["tts"]


class CoquiMetadata(BaseMetadata):
    """Coqui TTS UI display metadata."""

    name: str = "Coqui TTS"
    color: str = "#10B981"
    textIcon: str = "CQ"
