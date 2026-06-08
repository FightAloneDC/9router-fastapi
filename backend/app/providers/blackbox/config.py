"""Blackbox AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class BlackboxConfig(BaseProviderConfig):
    """Blackbox AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Blackbox AI"
    PROVIDER_ID: str = "blackbox"
    ALIAS: str = "bb"
    BASE_URL: str = "https://api.blackbox.ai/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class BlackboxMetadata(BaseMetadata):
    """Blackbox AI UI display metadata."""

    name: str = "Blackbox AI"
    color: str = "#5B5FEF"
    textIcon: str = "BB"
    icon: str = "Bot"
    website: str = "https://blackbox.ai"
    notice: dict | None = {"apiKeyUrl": "https://www.blackbox.ai/api-management"}
