"""xAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class XaiConfig(BaseProviderConfig):
    """xAI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "xAI"
    PROVIDER_ID: str = "xai"
    ALIAS: str = "xai"
    BASE_URL: str = "https://api.x.ai/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "webSearch"]


class XaiMetadata(BaseMetadata):
    """xAI UI display metadata."""

    name: str = "xAI"
    color: str = "#1DA1F2"
    textIcon: str = "XA"
    icon: str = "Sparkles"
    website: str = "https://console.x.ai"
    notice: dict | None = {"apiKeyUrl": "https://console.x.ai/"}
