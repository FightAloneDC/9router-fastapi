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
    MODEL_CATALOG_TABLE: bool = True
    # Free-variant caps (docs): per egress IP, not per API key.
    # Paid (non-:free) models have no OpenRouter request cap.
    # rpd 50 until $10 lifetime credits, then 1000. rpm stays 20.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free": {"rpm": 20, "rpd": 50},
        "payg": {"rpm": 20, "rpd": 1000},
        "subscribe": {"rpm": 20, "rpd": 1000},
    }


class OpenrouterMetadata(BaseMetadata):
    """OpenRouter UI display metadata."""

    name: str = "OpenRouter"
    color: str = "#F97316"
    textIcon: str = "OR"
    icon: str = "Router"
    website: str = "https://openrouter.ai"
    notice: dict | None = {
        "text": (
            "Free :free models: 20 RPM, 50 RPD (1000 RPD after "
            "$10 lifetime credits). Caps apply per egress IP."
        ),
        "apiKeyUrl": "https://openrouter.ai/settings/keys",
    }
