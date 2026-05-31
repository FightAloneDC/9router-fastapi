"""Vercel AI Gateway provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class VercelAIGatewayConfig(BaseModel):
    """Vercel AI Gateway provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Vercel AI Gateway"
    PROVIDER_ID: str = "vercel-ai-gateway"
    ALIAS: str = "vag"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://ai-gateway.vercel.sh/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class VercelAIGatewayMetadata(BaseModel):
    """Vercel AI Gateway UI display metadata."""

    name: str = "Vercel AI Gateway"
    color: str = "#000000"
    textIcon: str = "VA"
