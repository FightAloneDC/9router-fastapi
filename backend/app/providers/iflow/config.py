"""iFlow AI provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class IflowConfig(BaseProviderConfig):
    """iFlow AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "iFlow AI"
    PROVIDER_ID: str = "iflow"
    ALIAS: str = "if"
    BASE_URL: str = "https://iflow.cn"
    SERVICE_KINDS: list[str] = []
    CATEGORY: str = "free"
    HIDDEN: bool = True


class IflowMetadata(BaseMetadata):
    """iFlow AI UI display metadata."""

    name: str = "iFlow AI"
    color: str = "#6366F1"
    textIcon: str = "IF"
    icon: str = "Droplets"
    website: str = "https://iflow.cn"
    notice: dict | None = {"signupUrl": "https://iflow.cn"}
