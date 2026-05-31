"""Minimax (China) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class MinimaxCnConfig(BaseModel):
    """Minimax (China) provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Minimax (China)"
    PROVIDER_ID: str = "minimax-cn"
    ALIAS: str = "minimax-cn"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.minimax.chat/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class MinimaxCnMetadata(BaseModel):
    """Minimax (China) UI display metadata."""

    name: str = "Minimax (China)"
    color: str = "#DC2626"
    textIcon: str = "MC"
