"""SearchAPI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class SearchapiConfig(BaseProviderConfig):
    """SearchAPI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "SearchAPI"
    PROVIDER_ID: str = "searchapi"
    ALIAS: str = "sapi"
    BASE_URL: str = "https://www.searchapi.io/api/v1"
    SERVICE_KINDS: list[str] = ["webSearch"]


class SearchapiMetadata(BaseMetadata):
    """SearchAPI UI display metadata."""

    name: str = "SearchAPI"
    color: str = "#10B981"
    textIcon: str = "SA"
    icon: str = "Search"
    website: str = "https://www.searchapi.io"
    notice: dict | None = {"apiKeyUrl": "https://www.searchapi.io/dashboard"}
