"""Gemini provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GeminiConfig(BaseModel):
    """Gemini provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Gemini"
    PROVIDER_ID: str = "gemini"
    ALIAS: str = "gemini"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding', 'image', 'imageToText', 'webSearch', 'tts', 'stt']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class GeminiMetadata(BaseModel):
    """Gemini UI display metadata."""

    name: str = "Gemini"
    color: str = "#4285F4"
    textIcon: str = "GE"
