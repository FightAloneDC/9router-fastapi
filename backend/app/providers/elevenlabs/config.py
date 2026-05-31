"""ElevenLabs provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class ElevenlabsConfig(BaseModel):
    """ElevenLabs provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "ElevenLabs"
    PROVIDER_ID: str = "elevenlabs"
    ALIAS: str = "el"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.elevenlabs.io/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "xi-api-key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class ElevenlabsMetadata(BaseModel):
    """ElevenLabs UI display metadata."""

    name: str = "ElevenLabs"
    color: str = "#000000"
    textIcon: str = "EL"
