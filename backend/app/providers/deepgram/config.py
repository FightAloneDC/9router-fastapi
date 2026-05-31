"""Deepgram provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class DeepgramConfig(BaseModel):
    """Deepgram provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Deepgram"
    PROVIDER_ID: str = "deepgram"
    ALIAS: str = "dg"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.deepgram.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts', 'stt']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Token "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class DeepgramMetadata(BaseModel):
    """Deepgram UI display metadata."""

    name: str = "Deepgram"
    color: str = "#13EF93"
    textIcon: str = "DG"
