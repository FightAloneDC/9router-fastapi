"""BytePlus ModelArk provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ByteplusConfig(BaseProviderConfig):
    """BytePlus ModelArk provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "BytePlus ModelArk"
    PROVIDER_ID: str = "byteplus"
    ALIAS: str = "bpm"
    BASE_URL: str = "https://ark.ap-southeast.bytepluses.com/api/coding/v3"
    SERVICE_KINDS: list[str] = ["llm"]


class ByteplusMetadata(BaseMetadata):
    """BytePlus ModelArk UI display metadata."""

    name: str = "BytePlus ModelArk"
    color: str = "#2563EB"
    textIcon: str = "BP"
    icon: str = "Cloud"
    website: str = "https://console.byteplus.com/ark"
    notice: dict | None = {"text": "Free credits for new accounts.", "apiKeyUrl": "https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey"}
