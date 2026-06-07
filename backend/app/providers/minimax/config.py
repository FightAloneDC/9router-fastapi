"""Minimax Coding provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MinimaxConfig(BaseProviderConfig):
    """Minimax Coding provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Minimax Coding"
    PROVIDER_ID: str = "minimax"
    ALIAS: str = "minimax"
    BASE_URL: str = "https://api.minimax.chat/v1"
    FORMAT: str = "claude"
    SERVICE_KINDS: list[str] = ["llm", "image", "imageToText", "webSearch", "tts"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "speech-2.8-hd": "tts",
        "speech-2.8-turbo": "tts",
        "speech-2.6-hd": "tts",
        "speech-2.6-turbo": "tts",
        "speech-02-hd": "tts",
        "speech-02-turbo": "tts",
        "speech-01-hd": "tts",
        "speech-01-turbo": "tts",
    }


class MinimaxMetadata(BaseMetadata):
    """Minimax Coding UI display metadata."""

    name: str = "Minimax Coding"
    color: str = "#7C3AED"
    textIcon: str = "MM"
