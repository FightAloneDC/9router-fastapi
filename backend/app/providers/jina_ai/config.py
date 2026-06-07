"""Jina AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class JinaAiConfig(BaseProviderConfig):
    """Jina AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Jina AI"
    PROVIDER_ID: str = "jina-ai"
    ALIAS: str = "jina"
    BASE_URL: str = "https://api.jina.ai/v1"
    SERVICE_KINDS: list[str] = ["embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "jina-embeddings-v3": "embedding",
        "jina-embeddings-v2-base-en": "embedding",
        "jina-embeddings-v2-base-code": "embedding",
    }


class JinaAiMetadata(BaseMetadata):
    """Jina AI UI display metadata."""

    name: str = "Jina AI"
    color: str = "#2563EB"
    textIcon: str = "JA"
