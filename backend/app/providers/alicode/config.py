"""Alibaba provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AlicodeConfig(BaseProviderConfig):
    """Alibaba provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba"
    PROVIDER_ID: str = "alicode"
    ALIAS: str = "alicode"
    BASE_URL: str = "https://coding.dashscope.aliyuncs.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class AlicodeMetadata(BaseMetadata):
    """Alibaba UI display metadata."""

    name: str = "Alibaba"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
