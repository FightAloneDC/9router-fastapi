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

    # ── Auth ────────────────────────────────────────────────────────────
    # Gemini uses query-param auth (?key=), not header auth
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    AUTH_QUERY_PARAM: str = "key"


class GeminiMetadata(BaseMetadata):
    """Gemini UI display metadata."""

    name: str = "Gemini"
    color: str = "#4285F4"
    textIcon: str = "GE"
