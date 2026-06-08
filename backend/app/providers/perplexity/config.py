"""Perplexity provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class PerplexityConfig(BaseProviderConfig):
    """Perplexity provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Perplexity"
    PROVIDER_ID: str = "perplexity"
    ALIAS: str = "px"
    BASE_URL: str = "https://api.perplexity.ai"
    SERVICE_KINDS: list[str] = ["llm", "webSearch"]


class PerplexityMetadata(BaseMetadata):
    """Perplexity UI display metadata."""

    name: str = "Perplexity"
    color: str = "#1A73E8"
    textIcon: str = "PX"
    icon: str = "Search"
    website: str = "https://www.perplexity.ai"
    notice: dict | None = {"apiKeyUrl": "https://www.perplexity.ai/settings/api"}
