"""Minimax Coding provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class MinimaxConfig(BaseModel):
    """Minimax Coding provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Minimax Coding"
    PROVIDER_ID: str = "minimax"
    ALIAS: str = "minimax"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.minimax.chat/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm', 'image', 'imageToText', 'webSearch', 'tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class MinimaxMetadata(BaseModel):
    """Minimax Coding UI display metadata."""

    name: str = "Minimax Coding"
    color: str = "#7C3AED"
    textIcon: str = "MM"
