"""Firecrawl provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class FirecrawlConfig(BaseModel):
    """Firecrawl provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Firecrawl"
    PROVIDER_ID: str = "firecrawl"
    ALIAS: str = "fc"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.firecrawl.dev"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webFetch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class FirecrawlMetadata(BaseModel):
    """Firecrawl UI display metadata."""

    name: str = "Firecrawl"
    color: str = "#F97316"
    textIcon: str = "FC"
