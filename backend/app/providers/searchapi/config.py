"""SearchAPI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class SearchapiConfig(BaseModel):
    """SearchAPI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SearchAPI"
    PROVIDER_ID: str = "searchapi"
    ALIAS: str = "sapi"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://www.searchapi.io/api/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class SearchapiMetadata(BaseModel):
    """SearchAPI UI display metadata."""

    name: str = "SearchAPI"
    color: str = "#10B981"
    textIcon: str = "SA"
