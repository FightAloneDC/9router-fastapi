"""Volcengine Ark provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VolcengineConfig(BaseProviderConfig):
    """Volcengine Ark provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Volcengine Ark"
    PROVIDER_ID: str = "volcengine"
    ALIAS: str = "vk"
    BASE_URL: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    SERVICE_KINDS: list[str] = ["llm"]


class VolcengineMetadata(BaseMetadata):
    """Volcengine Ark UI display metadata."""

    name: str = "Volcengine Ark"
    color: str = "#000000"
    textIcon: str = "VK"
    icon: str = "Cloud"
