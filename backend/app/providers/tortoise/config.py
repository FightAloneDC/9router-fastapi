"""Tortoise TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class TortoiseConfig(BaseProviderConfig):
    """Tortoise TTS provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Tortoise TTS"
    PROVIDER_ID: str = "tortoise"
    ALIAS: str = "tt"
    BASE_URL: str = "http://localhost"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""


class TortoiseMetadata(BaseMetadata):
    """Tortoise TTS UI display metadata."""

    name: str = "Tortoise TTS"
    color: str = "#6B7280"
    textIcon: str = "TT"
