"""Cerebras provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CerebrasConfig(BaseModel):
    """Cerebras provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cerebras"
    PROVIDER_ID: str = "cerebras"
    ALIAS: str = "cb"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.cerebras.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ["llm"]

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CerebrasMetadata(BaseModel):
    """Cerebras UI display metadata."""

    name: str = "Cerebras"
    color: str = "#FF6B00"
    textIcon: str = "CB"
