"""OpenRouter provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class OpenrouterConfig(BaseModel):
    """OpenRouter provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenRouter"
    PROVIDER_ID: str = "openrouter"
    ALIAS: str = "openrouter"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://openrouter.ai/api/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding', 'imageToText', 'tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class OpenrouterMetadata(BaseModel):
    """OpenRouter UI display metadata."""

    name: str = "OpenRouter"
    color: str = "#F97316"
    textIcon: str = "OR"
