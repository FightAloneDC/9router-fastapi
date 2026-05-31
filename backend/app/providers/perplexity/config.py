"""Perplexity provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class PerplexityConfig(BaseModel):
    """Perplexity provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Perplexity"
    PROVIDER_ID: str = "perplexity"
    ALIAS: str = "px"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.perplexity.ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class PerplexityMetadata(BaseModel):
    """Perplexity UI display metadata."""

    name: str = "Perplexity"
    color: str = "#1A73E8"
    textIcon: str = "PX"
