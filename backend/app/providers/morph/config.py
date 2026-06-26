"""Morph provider definition.

OpenAI-compatible provider for Morph LLM.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MorphConfig(BaseProviderConfig):
    """Morph provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Morph"
    PROVIDER_ID: str = "morph"
    ALIAS: str = "mo"
    BASE_URL: str = "https://api.morphllm.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class MorphMetadata(BaseMetadata):
    """Morph UI display metadata."""

    name: str = "Morph"
    color: str = "#6366F1"
    textIcon: str = "MO"
    icon: str = "/providers/morph.png"
    website: str = "https://www.morphllm.com"
    notice: dict | None = {
        "apiKeyUrl": "https://www.morphllm.com",
    }
