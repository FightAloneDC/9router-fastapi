"""AskCodi provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AskCodiConfig(BaseModel):
    """AskCodi provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "AskCodi"
    PROVIDER_ID: str = "askcodi"
    ALIAS: str = "ac"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.askcodi.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AskCodiMetadata(BaseModel):
    """AskCodi UI display metadata."""

    name: str = "AskCodi"
    color: str = "#6366F1"
    textIcon: str = "AC"
