"""Vertex Partner provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class VertexPartnerConfig(BaseModel):
    """Vertex Partner provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vertex Partner"
    PROVIDER_ID: str = "vertex-partner"
    ALIAS: str = "vxp"

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


class VertexPartnerMetadata(BaseModel):
    """Vertex Partner UI display metadata."""

    name: str = "Vertex Partner"
    color: str = "#34A853"
    textIcon: str = "VP"
