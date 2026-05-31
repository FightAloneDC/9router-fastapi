"""Linkup provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class LinkupConfig(BaseModel):
    """Linkup provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Linkup"
    PROVIDER_ID: str = "linkup"
    ALIAS: str = "lk"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.linkup.so"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class LinkupMetadata(BaseModel):
    """Linkup UI display metadata."""

    name: str = "Linkup"
    color: str = "#3B82F6"
    textIcon: str = "LK"
