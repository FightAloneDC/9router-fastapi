"""Google PSE provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GooglePSEConfig(BaseModel):
    """Google PSE provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Google PSE"
    PROVIDER_ID: str = "google-pse"
    ALIAS: str = "gpse"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://www.googleapis.com/customsearch/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class GooglePSEMetadata(BaseModel):
    """Google PSE UI display metadata."""

    name: str = "Google PSE"
    color: str = "#4285F4"
    textIcon: str = "GP"
