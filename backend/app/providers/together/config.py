"""Together provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class TogetherConfig(BaseProviderConfig):
    """Together provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Together"
    PROVIDER_ID: str = "together"
    ALIAS: str = "tg"
    BASE_URL: str = "https://api.together.xyz/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]


class TogetherMetadata(BaseMetadata):
    """Together UI display metadata."""

    name: str = "Together"
    color: str = "#6C3AED"
    textIcon: str = "TG"
