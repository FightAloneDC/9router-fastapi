"""Mistral provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class MistralConfig(BaseModel):
    """Mistral provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Mistral"
    PROVIDER_ID: str = "mistral"
    ALIAS: str = "mi"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.mistral.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'imageToText', 'embedding']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class MistralMetadata(BaseModel):
    """Mistral UI display metadata."""

    name: str = "Mistral"
    color: str = "#FF7000"
    textIcon: str = "MI"
