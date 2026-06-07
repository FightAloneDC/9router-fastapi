"""PlayHT provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class PlayhtConfig(BaseProviderConfig):
    """PlayHT provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "PlayHT"
    PROVIDER_ID: str = "playht"
    ALIAS: str = "pht"
    BASE_URL: str = "https://api.play.ht/v2"
    SERVICE_KINDS: list[str] = ["tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "PlayDialog": "tts",
        "Play3.0-mini": "tts",
    }


class PlayhtMetadata(BaseMetadata):
    """PlayHT UI display metadata."""

    name: str = "PlayHT"
    color: str = "#F59E0B"
    textIcon: str = "PH"
