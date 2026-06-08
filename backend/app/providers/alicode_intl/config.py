"""Alibaba Intl provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AlicodeIntlConfig(BaseProviderConfig):
    """Alibaba Intl provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba Intl"
    PROVIDER_ID: str = "alicode-intl"
    ALIAS: str = "alicode-intl"
    BASE_URL: str = "https://coding-intl.dashscope.aliyuncs.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class AlicodeIntlMetadata(BaseMetadata):
    """Alibaba Intl UI display metadata."""

    name: str = "Alibaba Intl"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
    icon: str = "Cloud"
    website: str = "https://modelstudio.console.alibabacloud.com"
    notice: dict | None = {"apiKeyUrl": "https://modelstudio.console.alibabacloud.com/?apiKey=***"}
