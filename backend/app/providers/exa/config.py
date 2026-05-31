"""Exa provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class ExaConfig(BaseModel):
    """Exa provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Exa"
    PROVIDER_ID: str = "exa"
    ALIAS: str = "exa"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.exa.ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch', 'webFetch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class ExaMetadata(BaseModel):
    """Exa UI display metadata."""

    name: str = "Exa"
    color: str = "#2563EB"
    textIcon: str = "EX"
