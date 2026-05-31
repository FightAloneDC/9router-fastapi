"""Nebius AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class NebiusConfig(BaseModel):
    """Nebius AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Nebius AI"
    PROVIDER_ID: str = "nebius"
    ALIAS: str = "nb"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.studio.nebius.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class NebiusMetadata(BaseModel):
    """Nebius AI UI display metadata."""

    name: str = "Nebius AI"
    color: str = "#00A3FF"
    textIcon: str = "NB"
