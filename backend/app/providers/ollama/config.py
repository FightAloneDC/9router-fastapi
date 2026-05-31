"""Ollama Cloud provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class OllamaConfig(BaseModel):
    """Ollama Cloud provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Ollama Cloud"
    PROVIDER_ID: str = "ollama"
    ALIAS: str = "ollama"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://ollama.com/api"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class OllamaMetadata(BaseModel):
    """Ollama Cloud UI display metadata."""

    name: str = "Ollama Cloud"
    color: str = "#FFFFFF"
    textIcon: str = "OL"
