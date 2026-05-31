"""Kilo Gateway provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class KiloGatewayConfig(BaseModel):
    """Kilo Gateway provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Kilo Gateway"
    PROVIDER_ID: str = "kilo-gateway"
    ALIAS: str = "kg"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.kilo.ai/api/gateway"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class KiloGatewayMetadata(BaseModel):
    """Kilo Gateway UI display metadata."""

    name: str = "Kilo Gateway"
    color: str = "#FF6B35"
    textIcon: str = "KG"
