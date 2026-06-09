"""Ollama Cloud provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OllamaConfig(BaseProviderConfig):
    """Ollama Cloud provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Ollama Cloud"
    PROVIDER_ID: str = "ollama"
    ALIAS: str = "ollama"
    BASE_URL: str = "https://ollama.com/api"
    SERVICE_KINDS: list[str] = ["llm"]
    CATEGORY: str = "freeTier"


class OllamaMetadata(BaseMetadata):
    """Ollama Cloud UI display metadata."""

    name: str = "Ollama Cloud"
    color: str = "#FFFFFF"
    textIcon: str = "OL"
    icon: str = "Cloud"
    website: str = "https://ollama.com"
    notice: dict | None = {"text": "Free tier: light usage, 1 cloud model at a time.", "apiKeyUrl": "https://ollama.com/settings/keys"}
