"""Crawl4AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class Crawl4AIConfig(BaseModel):
    """Crawl4AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Crawl4AI"
    PROVIDER_ID: str = "crawl4ai"
    ALIAS: str = "c4ai"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.crawl4ai.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webFetch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class Crawl4AIMetadata(BaseModel):
    """Crawl4AI UI display metadata."""

    name: str = "Crawl4AI"
    color: str = "#06B6D4"
    textIcon: str = "C4"
