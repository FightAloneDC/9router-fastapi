"""Xiaomi MiMo provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class XiaomiMimoConfig(BaseProviderConfig):
    """Xiaomi MiMo provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Xiaomi MiMo"
    PROVIDER_ID: str = "xiaomi-mimo"
    ALIAS: str = "mimo"
    BASE_URL: str = "https://api.xiaomimimo.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class XiaomiMimoMetadata(BaseMetadata):
    """Xiaomi MiMo UI display metadata."""

    name: str = "Xiaomi MiMo"
    color: str = "#FF6900"
    textIcon: str = "XM"
