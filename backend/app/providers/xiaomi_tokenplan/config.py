"""Xiaomi MiMo (Token Plan) provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class XiaomiTokenplanConfig(BaseProviderConfig):
    """Xiaomi MiMo (Token Plan) provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Xiaomi MiMo (Token Plan)"
    PROVIDER_ID: str = "xiaomi-tokenplan"
    ALIAS: str = "xmtp"
    BASE_URL: str = "https://api.xiaomimimo.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class XiaomiTokenplanMetadata(BaseMetadata):
    """Xiaomi MiMo (Token Plan) UI display metadata."""

    name: str = "Xiaomi MiMo (Token Plan)"
    color: str = "#FF6700"
    textIcon: str = "XT"
