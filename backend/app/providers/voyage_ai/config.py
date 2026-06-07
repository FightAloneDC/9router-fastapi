"""Voyage AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VoyageAiConfig(BaseProviderConfig):
    """Voyage AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Voyage AI"
    PROVIDER_ID: str = "voyage-ai"
    ALIAS: str = "voyage"
    BASE_URL: str = "https://api.voyageai.com/v1"
    SERVICE_KINDS: list[str] = ["embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "voyage-3-large": "embedding",
        "voyage-3.5": "embedding",
        "voyage-3.5-lite": "embedding",
        "voyage-code-3": "embedding",
        "voyage-finance-2": "embedding",
        "voyage-law-2": "embedding",
        "voyage-multilingual-2": "embedding",
    }


class VoyageAiMetadata(BaseMetadata):
    """Voyage AI UI display metadata."""

    name: str = "Voyage AI"
    color: str = "#FF6B6B"
    textIcon: str = "VY"
