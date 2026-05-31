"""Blackbox AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class BlackboxConfig(BaseModel):
    """Blackbox AI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Blackbox AI"
    PROVIDER_ID: str = "blackbox"
    ALIAS: str = "bb"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.blackbox.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BlackboxMetadata(BaseModel):
    """Blackbox AI UI display metadata."""

    name: str = "Blackbox AI"
    color: str = "#5B5FEF"
    textIcon: str = "BB"
