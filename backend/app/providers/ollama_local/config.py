"""Ollama Local provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OllamaLocalConfig(BaseProviderConfig):
    """Ollama Local provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Ollama Local"
    PROVIDER_ID: str = "ollama-local"
    ALIAS: str = "ollama-local"
    BASE_URL: str = "http://localhost:11434"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""


class OllamaLocalMetadata(BaseMetadata):
    """Ollama Local UI display metadata."""

    name: str = "Ollama Local"
    color: str = "#FFFFFF"
    textIcon: str = "OL"
    icon: str = "Cloud"
    website: str = "https://ollama.com"
