"""Tavily provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class TavilyConfig(BaseModel):
    """Tavily provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Tavily"
    PROVIDER_ID: str = "tavily"
    ALIAS: str = "tavily"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.tavily.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch', 'webFetch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class TavilyMetadata(BaseModel):
    """Tavily UI display metadata."""

    name: str = "Tavily"
    color: str = "#5B21B6"
    textIcon: str = "TV"
