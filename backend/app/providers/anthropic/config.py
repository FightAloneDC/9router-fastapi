"""Anthropic provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class AnthropicConfig(BaseModel):
    """Anthropic provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Anthropic"
    PROVIDER_ID: str = "anthropic"
    ALIAS: str = "an"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.anthropic.com/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'imageToText']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "x-api-key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {'anthropic-version': '2023-06-01'}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class AnthropicMetadata(BaseModel):
    """Anthropic UI display metadata."""

    name: str = "Anthropic"
    color: str = "#D97757"
    textIcon: str = "AC"
