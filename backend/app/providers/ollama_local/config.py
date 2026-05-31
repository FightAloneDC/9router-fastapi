"""Ollama Local provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class OllamaLocalConfig(BaseModel):
    """Ollama Local provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Ollama Local"
    PROVIDER_ID: str = "ollama-local"
    ALIAS: str = "ollama-local"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "http://localhost:11434"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['llm']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class OllamaLocalMetadata(BaseModel):
    """Ollama Local UI display metadata."""

    name: str = "Ollama Local"
    color: str = "#FFFFFF"
    textIcon: str = "OL"
