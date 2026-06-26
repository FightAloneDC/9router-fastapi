"""MiMo Code Free provider definition.

Free AI models via MiMo Code CLI. No API key required.
Uses bootstrap JWT flow with anti-abuse measures.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MimoFreeConfig(BaseProviderConfig):
    """MiMo Code Free provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "MiMo Code Free"
    PROVIDER_ID: str = "mimo-free"
    ALIAS: str = "mmf"
    BASE_URL: str = "https://api.xiaomimimo.com/api/free-ai/openai"
    SERVICE_KINDS: list[str] = ["llm"]
    CATEGORY: str = "free"
    NO_AUTH: bool = True
    MODELS_FETCHER: dict | None = None


class MimoFreeMetadata(BaseMetadata):
    """MiMo Code Free UI display metadata."""

    name: str = "MiMo Code Free"
    color: str = "#FF6900"
    textIcon: str = "MF"
    icon: str = "smart_toy"
    website: str = "https://xiaomimimo.com"
    notice: dict | None = {
        "text": "Free AI models via MiMo Code CLI. No API key required.",
    }
