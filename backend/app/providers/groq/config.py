"""Groq provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GroqConfig(BaseProviderConfig):
    """Groq provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Groq"
    PROVIDER_ID: str = "groq"
    ALIAS: str = "gq"
    BASE_URL: str = "https://api.groq.com/openai/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "stt"]


class GroqMetadata(BaseMetadata):
    """Groq UI display metadata."""

    name: str = "Groq"
    color: str = "#F55036"
    textIcon: str = "GQ"
