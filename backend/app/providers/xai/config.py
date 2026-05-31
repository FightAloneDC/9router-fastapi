"""xAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class XAIConfig(BaseModel):
    """xAI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "xAI"
    PROVIDER_ID: str = "xai"
    ALIAS: str = "xai"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.x.ai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'imageToText', 'webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class XAIMetadata(BaseModel):
    """xAI UI display metadata."""

    name: str = "xAI"
    color: str = "#1DA1F2"
    textIcon: str = "XA"
