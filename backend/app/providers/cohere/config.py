"""Cohere provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CohereConfig(BaseModel):
    """Cohere provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cohere"
    PROVIDER_ID: str = "cohere"
    ALIAS: str = "co"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.cohere.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CohereMetadata(BaseModel):
    """Cohere UI display metadata."""

    name: str = "Cohere"
    color: str = "#39594D"
    textIcon: str = "CO"
