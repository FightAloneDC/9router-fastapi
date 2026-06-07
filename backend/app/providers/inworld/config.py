"""Inworld AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class InworldConfig(BaseProviderConfig):
    """Inworld AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Inworld AI"
    PROVIDER_ID: str = "inworld"
    ALIAS: str = "iw"
    BASE_URL: str = "https://api.inworld.ai"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Basic "

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "inworld-tts-1.5-mini": "tts",
        "inworld-tts-1.5-max": "tts",
    }


class InworldMetadata(BaseMetadata):
    """Inworld AI UI display metadata."""

    name: str = "Inworld AI"
    color: str = "#7C3AED"
    textIcon: str = "IW"
