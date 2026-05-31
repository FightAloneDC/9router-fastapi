"""You.com provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class YouComConfig(BaseModel):
    """You.com provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "You.com"
    PROVIDER_ID: str = "you-com"
    ALIAS: str = "you"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.you.com"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class YouComMetadata(BaseModel):
    """You.com UI display metadata."""

    name: str = "You.com"
    color: str = "#8B5CF6"
    textIcon: str = "YC"
