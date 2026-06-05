"""Google PSE provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GooglePseConfig(BaseProviderConfig):
    """Google PSE provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Google PSE"
    PROVIDER_ID: str = "google-pse"
    ALIAS: str = "gpse"
    BASE_URL: str = "https://www.googleapis.com/customsearch/v1"
    SERVICE_KINDS: list[str] = ["webSearch"]


class GooglePseMetadata(BaseMetadata):
    """Google PSE UI display metadata."""

    name: str = "Google PSE"
    color: str = "#4285F4"
    textIcon: str = "GP"
