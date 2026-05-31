"""Nanobanana provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class NanobananaConfig(BaseModel):
    """Nanobanana provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Nanobanana"
    PROVIDER_ID: str = "nanobanana"
    ALIAS: str = "nana"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.nanobananaapi.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class NanobananaMetadata(BaseModel):
    """Nanobanana UI display metadata."""

    name: str = "Nanobanana"
    color: str = "#F59E0B"
    textIcon: str = "NB"
