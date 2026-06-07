"""Kimi provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class KimiConfig(BaseProviderConfig):
    """Kimi provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Kimi"
    PROVIDER_ID: str = "kimi"
    ALIAS: str = "kimi"
    BASE_URL: str = "https://api.moonshot.cn/v1"
    FORMAT: str = "claude"
    SERVICE_KINDS: list[str] = ["llm", "webSearch"]


class KimiMetadata(BaseMetadata):
    """Kimi UI display metadata."""

    name: str = "Kimi"
    color: str = "#1E3A8A"
    textIcon: str = "KM"
