"""Runway ML provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class RunwaymlConfig(BaseModel):
    """Runway ML provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Runway ML"
    PROVIDER_ID: str = "runwayml"
    ALIAS: str = "runway"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.dev.runwayml.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image', 'video']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class RunwaymlMetadata(BaseModel):
    """Runway ML UI display metadata."""

    name: str = "Runway ML"
    color: str = "#000000"
    textIcon: str = "RW"
