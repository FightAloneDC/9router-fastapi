"""Stability AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class StabilityAIConfig(BaseModel):
    """Stability AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Stability AI"
    PROVIDER_ID: str = "stability-ai"
    ALIAS: str = "stability"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.stability.ai/v2beta"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class StabilityAIMetadata(BaseModel):
    """Stability AI UI display metadata."""

    name: str = "Stability AI"
    color: str = "#8B5CF6"
    textIcon: str = "SA"
