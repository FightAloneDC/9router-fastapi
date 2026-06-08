"""Volcengine Ark provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VolcengineArkConfig(BaseProviderConfig):
    """Volcengine Ark provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Volcengine Ark"
    PROVIDER_ID: str = "volcengine-ark"
    ALIAS: str = "ark"
    BASE_URL: str = "https://ark.cn-beijing.volces.com/api/coding/v3"
    SERVICE_KINDS: list[str] = ["llm"]


class VolcengineArkMetadata(BaseMetadata):
    """Volcengine Ark UI display metadata."""

    name: str = "Volcengine Ark"
    color: str = "#1677FF"
    textIcon: str = "ARK"
    icon: str = "Cloud"
    website: str = "https://ark.cn-beijing.volces.com"
    notice: dict | None = {"apiKeyUrl": "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey"}
