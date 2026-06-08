"""Kiro AI provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class KiroConfig(BaseProviderConfig):
    """Kiro AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Kiro AI"
    PROVIDER_ID: str = "kiro"
    ALIAS: str = "kr"
    BASE_URL: str = "https://kiro.ai"
    SERVICE_KINDS: list[str] = ["llm", "tts"]
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."
    CUSTOM_MODAL: str = "kiro"


class KiroMetadata(BaseMetadata):
    """Kiro AI UI display metadata."""

    name: str = "Kiro AI"
    color: str = "#FF6B35"
    textIcon: str = "KR"
    icon: str = "Brain"
    website: str = "https://kiro.dev"
    notice: dict | None = {"signupUrl": "https://kiro.dev"}
