"""Jina AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class JinaAIConfig(BaseModel):
    """Jina AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Jina AI"
    PROVIDER_ID: str = "jina-ai"
    ALIAS: str = "jina"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.jina.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class JinaAIMetadata(BaseModel):
    """Jina AI UI display metadata."""

    name: str = "Jina AI"
    color: str = "#2563EB"
    textIcon: str = "JA"
