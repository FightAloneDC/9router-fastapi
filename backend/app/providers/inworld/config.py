"""Inworld AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class InworldConfig(BaseModel):
    """Inworld AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Inworld AI"
    PROVIDER_ID: str = "inworld"
    ALIAS: str = "iw"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.inworld.ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class InworldMetadata(BaseModel):
    """Inworld AI UI display metadata."""

    name: str = "Inworld AI"
    color: str = "#7C3AED"
    textIcon: str = "IW"
