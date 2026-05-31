"""Brave Search provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class BraveSearchConfig(BaseModel):
    """Brave Search provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Brave Search"
    PROVIDER_ID: str = "brave-search"
    ALIAS: str = "brave"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.search.brave.com/res/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BraveSearchMetadata(BaseModel):
    """Brave Search UI display metadata."""

    name: str = "Brave Search"
    color: str = "#FB542B"
    textIcon: str = "BR"
