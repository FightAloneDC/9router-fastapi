"""Jina Reader provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class JinaReaderConfig(BaseProviderConfig):
    """Jina Reader provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Jina Reader"
    PROVIDER_ID: str = "jina-reader"
    ALIAS: str = "jinar"
    BASE_URL: str = "https://r.jina.ai"
    SERVICE_KINDS: list[str] = ["webFetch"]


class JinaReaderMetadata(BaseMetadata):
    """Jina Reader UI display metadata."""

    name: str = "Jina Reader"
    color: str = "#000000"
    textIcon: str = "JR"
