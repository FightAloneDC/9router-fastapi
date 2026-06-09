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
    REGIONS: list[dict] | None = [{"id": "sgp", "label": "Singapore"}, {"id": "cn", "label": "China"}, {"id": "ams", "label": "Europe"}]
    DEFAULT_REGION: str = "sgp"
    PROVIDER_SPECIFIC_DATA: bool = True


class XiaomiTokenplanMetadata(BaseMetadata):
    """Xiaomi MiMo (Token Plan) UI display metadata."""

    name: str = "Xiaomi MiMo (Token Plan)"
    color: str = "#FF6700"
    textIcon: str = "XT"
    icon: str = "Bot"
    website: str = "https://mimo.xiaomi.com"
    notice: dict | None = {"text": "Xiaomi MiMo Token Plan subscription.", "apiKeyUrl": "https://mimo.xiaomi.com"}
