"""Mistral provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MistralConfig(BaseProviderConfig):
    """Mistral provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Mistral"
    PROVIDER_ID: str = "mistral"
    ALIAS: str = "mi"
    BASE_URL: str = "https://api.mistral.ai/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "embedding"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "mistral-embed": "embedding",
    }


class MistralMetadata(BaseMetadata):
    """Mistral UI display metadata."""

    name: str = "Mistral"
    color: str = "#FF7000"
    textIcon: str = "MI"
