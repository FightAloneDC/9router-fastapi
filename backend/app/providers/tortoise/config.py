"""Tortoise TTS provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class TortoiseConfig(BaseModel):
    """Tortoise TTS provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Tortoise TTS"
    PROVIDER_ID: str = "tortoise"
    ALIAS: str = "tt"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class TortoiseMetadata(BaseModel):
    """Tortoise TTS UI display metadata."""

    name: str = "Tortoise TTS"
    color: str = "#6B7280"
    textIcon: str = "TT"
