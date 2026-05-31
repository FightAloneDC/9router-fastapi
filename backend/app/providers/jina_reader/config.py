"""Jina Reader provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class JinaReaderConfig(BaseModel):
    """Jina Reader provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Jina Reader"
    PROVIDER_ID: str = "jina-reader"
    ALIAS: str = "jinar"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://r.jina.ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webFetch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class JinaReaderMetadata(BaseModel):
    """Jina Reader UI display metadata."""

    name: str = "Jina Reader"
    color: str = "#000000"
    textIcon: str = "JR"
