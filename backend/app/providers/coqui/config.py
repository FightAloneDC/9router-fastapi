"""Coqui TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CoquiConfig(BaseModel):
    """Coqui TTS provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Coqui TTS"
    PROVIDER_ID: str = "coqui"
    ALIAS: str = "cq"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://app.coqui.ai/api/v2"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CoquiMetadata(BaseModel):
    """Coqui TTS UI display metadata."""

    name: str = "Coqui TTS"
    color: str = "#10B981"
    textIcon: str = "CQ"
