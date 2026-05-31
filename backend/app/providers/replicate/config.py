"""Replicate provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class ReplicateConfig(BaseModel):
    """Replicate provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Replicate"
    PROVIDER_ID: str = "replicate"
    ALIAS: str = "rep"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.replicate.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class ReplicateMetadata(BaseModel):
    """Replicate UI display metadata."""

    name: str = "Replicate"
    color: str = "#000000"
    textIcon: str = "RP"
