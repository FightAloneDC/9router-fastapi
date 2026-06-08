"""Grok Web (Subscription) provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GrokWebConfig(BaseProviderConfig):
    """Grok Web (Subscription) provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Grok Web (Subscription)"
    PROVIDER_ID: str = "grok-web"
    ALIAS: str = "gw"
    BASE_URL: str = "https://grok.com"
    SERVICE_KINDS: list[str] = ["llm"]
    PASSTHROUGH_MODELS: bool = True


class GrokWebMetadata(BaseMetadata):
    """Grok Web (Subscription) UI display metadata."""

    name: str = "Grok Web (Subscription)"
    color: str = "#1DA1F2"
    textIcon: str = "GW"
    icon: str = "Sparkles"
    website: str = "https://grok.com"
    notice: dict | None = {"authHint": "Paste your sso= cookie value from grok.com"}
