"""Vertex AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class VertexConfig(BaseModel):
    """Vertex AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vertex AI"
    PROVIDER_ID: str = "vertex"
    ALIAS: str = "vx"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://aiplatform.googleapis.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class VertexMetadata(BaseModel):
    """Vertex AI UI display metadata."""

    name: str = "Vertex AI"
    color: str = "#4285F4"
    textIcon: str = "VX"
