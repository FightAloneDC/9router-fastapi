"""Hyperbolic provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class HyperbolicConfig(BaseModel):
    """Hyperbolic provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Hyperbolic"
    PROVIDER_ID: str = "hyperbolic"
    ALIAS: str = "hyp"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.hyperbolic.xyz/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class HyperbolicMetadata(BaseModel):
    """Hyperbolic UI display metadata."""

    name: str = "Hyperbolic"
    color: str = "#8B5CF6"
    textIcon: str = "HY"
