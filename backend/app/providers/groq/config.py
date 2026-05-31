"""Groq provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class GroqConfig(BaseModel):
    """Groq provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Groq"
    PROVIDER_ID: str = "groq"
    ALIAS: str = "gq"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.groq.com/openai/v1"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "stt"]

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class GroqMetadata(BaseModel):
    """Groq UI display metadata."""

    name: str = "Groq"
    color: str = "#F55036"
    textIcon: str = "GQ"
