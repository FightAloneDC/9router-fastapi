"""Cartesia provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class CartesiaConfig(BaseModel):
    """Cartesia provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cartesia"
    PROVIDER_ID: str = "cartesia"
    ALIAS: str = "cart"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.cartesia.ai"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "X-API-Key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {"Cartesia-Version": "2024-06-10"}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class CartesiaMetadata(BaseModel):
    """Cartesia UI display metadata."""

    name: str = "Cartesia"
    color: str = "#06B6D4"
    textIcon: str = "CA"
