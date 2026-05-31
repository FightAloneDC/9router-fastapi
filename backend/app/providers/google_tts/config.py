"""Google TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GoogleTTSConfig(BaseModel):
    """Google TTS provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Google TTS"
    PROVIDER_ID: str = "google-tts"
    ALIAS: str = "gtts"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://texttospeech.googleapis.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class GoogleTTSMetadata(BaseModel):
    """Google TTS UI display metadata."""

    name: str = "Google TTS"
    color: str = "#4285F4"
    textIcon: str = "GT"
