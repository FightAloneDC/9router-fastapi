"""Fireworks provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class FireworksConfig(BaseModel):
    """Fireworks provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Fireworks"
    PROVIDER_ID: str = "fireworks"
    ALIAS: str = "fw"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.fireworks.ai/inference/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class FireworksMetadata(BaseModel):
    """Fireworks UI display metadata."""

    name: str = "Fireworks"
    color: str = "#FF4F00"
    textIcon: str = "FW"
