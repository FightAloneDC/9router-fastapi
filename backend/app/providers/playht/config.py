"""PlayHT provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class PlayhtConfig(BaseModel):
    """PlayHT provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "PlayHT"
    PROVIDER_ID: str = "playht"
    ALIAS: str = "pht"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.play.ht/v2"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class PlayhtMetadata(BaseModel):
    """PlayHT UI display metadata."""

    name: str = "PlayHT"
    color: str = "#F59E0B"
    textIcon: str = "PH"
