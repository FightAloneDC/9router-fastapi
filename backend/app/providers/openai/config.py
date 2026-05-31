"""OpenAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class OpenAIConfig(BaseModel):
    """OpenAI provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenAI"
    PROVIDER_ID: str = "openai"
    ALIAS: str = "openai"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.openai.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'embedding', 'tts', 'stt', 'image', 'imageToText', 'webSearch']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class OpenAIMetadata(BaseModel):
    """OpenAI UI display metadata."""

    name: str = "OpenAI"
    color: str = "#10A37F"
    textIcon: str = "OA"
