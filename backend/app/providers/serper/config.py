"""Serper provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class SerperConfig(BaseModel):
    """Serper provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Serper"
    PROVIDER_ID: str = "serper"
    ALIAS: str = "serper"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://serper.dev/api"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class SerperMetadata(BaseModel):
    """Serper UI display metadata."""

    name: str = "Serper"
    color: str = "#4F46E5"
    textIcon: str = "SP"
