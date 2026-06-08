"""Cohere provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CohereConfig(BaseProviderConfig):
    """Cohere provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cohere"
    PROVIDER_ID: str = "cohere"
    ALIAS: str = "co"
    BASE_URL: str = "https://api.cohere.com/compatibility/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]


class CohereMetadata(BaseMetadata):
    """Cohere UI display metadata."""

    name: str = "Cohere"
    color: str = "#39594D"
    textIcon: str = "CO"
    icon: str = "Sparkles"
    website: str = "https://dashboard.cohere.com"
    notice: dict | None = {"apiKeyUrl": "https://dashboard.cohere.com/api-keys"}
