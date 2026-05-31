"""Topaz provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class TopazConfig(BaseModel):
    """Topaz provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Topaz"
    PROVIDER_ID: str = "topaz"
    ALIAS: str = "topaz"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.topazlabs.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class TopazMetadata(BaseModel):
    """Topaz UI display metadata."""

    name: str = "Topaz"
    color: str = "#059669"
    textIcon: str = "TP"
