"""Voyage AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class VoyageAIConfig(BaseModel):
    """Voyage AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Voyage AI"
    PROVIDER_ID: str = "voyage-ai"
    ALIAS: str = "voyage"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.voyageai.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class VoyageAIMetadata(BaseModel):
    """Voyage AI UI display metadata."""

    name: str = "Voyage AI"
    color: str = "#FF6B6B"
    textIcon: str = "VY"
