"""Black Forest Labs provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class BflConfig(BaseModel):
    """Black Forest Labs provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Black Forest Labs"
    PROVIDER_ID: str = "bfl"
    ALIAS: str = "bfl"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.bfl.ml"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class BflMetadata(BaseModel):
    """Black Forest Labs UI display metadata."""

    name: str = "Black Forest Labs"
    color: str = "#1E40AF"
    textIcon: str = "BF"
