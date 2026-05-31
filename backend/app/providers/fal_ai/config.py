"""Fal.ai provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class FalAIConfig(BaseModel):
    """Fal.ai provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Fal.ai"
    PROVIDER_ID: str = "fal-ai"
    ALIAS: str = "fal"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.fal.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class FalAIMetadata(BaseModel):
    """Fal.ai UI display metadata."""

    name: str = "Fal.ai"
    color: str = "#2563EB"
    textIcon: str = "FL"
