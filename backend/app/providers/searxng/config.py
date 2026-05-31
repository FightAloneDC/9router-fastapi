"""SearXNG provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class SearxngConfig(BaseModel):
    """SearXNG provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SearXNG"
    PROVIDER_ID: str = "searxng"
    ALIAS: str = "sx"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost:8080"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class SearxngMetadata(BaseModel):
    """SearXNG UI display metadata."""

    name: str = "SearXNG"
    color: str = "#FF6B35"
    textIcon: str = "SX"
