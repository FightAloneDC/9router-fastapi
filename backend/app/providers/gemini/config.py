"""Gemini provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GeminiConfig(BaseProviderConfig):
    """Gemini provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Gemini"
    PROVIDER_ID: str = "gemini"
    ALIAS: str = "gemini"
    BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "image", "imageToText", "webSearch", "tts", "stt"]
    CATEGORY: str = "freeTier"

    # ── Auth ────────────────────────────────────────────────────────────
    # Gemini uses query-param auth (?key=), not header auth
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    AUTH_QUERY_PARAM: str = "key"

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "gemini-2.5-flash-preview-tts": "tts",
        "gemini-2.5-pro-preview-tts": "tts",
        "text-embedding-004": "embedding",
        "embedding-001": "embedding",
    }
    MEDIA_PRIORITY: int = 1


class GeminiMetadata(BaseMetadata):
    """Gemini UI display metadata."""

    name: str = "Gemini"
    color: str = "#4285F4"
    textIcon: str = "GE"
    icon: str = "Diamond"
    website: str = "https://ai.google.dev"
    notice: dict | None = {"apiKeyUrl": "https://aistudio.google.com/app/apikey"}
