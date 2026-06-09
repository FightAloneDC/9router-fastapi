"""OpenRouter provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OpenrouterConfig(BaseProviderConfig):
    """OpenRouter provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenRouter"
    PROVIDER_ID: str = "openrouter"
    ALIAS: str = "openrouter"
    BASE_URL: str = "https://openrouter.ai/api/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "imageToText", "tts"]
    CATEGORY: str = "freeTier"


class OpenrouterMetadata(BaseMetadata):
    """OpenRouter UI display metadata."""

    name: str = "OpenRouter"
    color: str = "#F97316"
    textIcon: str = "OR"
    icon: str = "Router"
    website: str = "https://openrouter.ai"
    notice: dict | None = {"text": "Free tier: 27+ free models, no credit card needed, 200 req/day.", "apiKeyUrl": "https://openrouter.ai/settings/keys"}
