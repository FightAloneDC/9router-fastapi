"""Base provider configuration — shared defaults for all providers.

Child classes override identity fields (PROVIDER_NAME, PROVIDER_ID, ALIAS,
BASE_URL, SERVICE_KINDS) and inherit connection/auth defaults.
"""

from pydantic import BaseModel


class BaseProviderConfig(BaseModel):
    """Base config for all providers.

    Covers header-based auth (default Bearer) and query-param auth (Gemini).
    Runtime data (API keys, custom baseUrl) come from ProviderConnection.data
    in the database — not from this config.
    """

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str
    PROVIDER_ID: str
    ALIAS: str
    BASE_URL: str

    # ── Connection defaults ─────────────────────────────────────────────
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = []

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}
    AUTH_QUERY_PARAM: str = ""  # non-empty for query-param auth (e.g. Gemini: "key")

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BaseMetadata(BaseModel):
    """UI display metadata for a provider."""

    name: str
    color: str
    textIcon: str
