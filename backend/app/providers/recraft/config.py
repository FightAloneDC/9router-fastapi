"""Recraft provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class RecraftConfig(BaseModel):
    """Recraft provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Recraft"
    PROVIDER_ID: str = "recraft"
    ALIAS: str = "recraft"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://external.api.recraft.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class RecraftMetadata(BaseModel):
    """Recraft UI display metadata."""

    name: str = "Recraft"
    color: str = "#EC4899"
    textIcon: str = "RC"
