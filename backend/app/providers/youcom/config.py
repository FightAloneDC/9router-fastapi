"""You.com provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class YoucomConfig(BaseProviderConfig):
    """You.com provider configuration."""

    PROVIDER_NAME: str = "You.com"
    PROVIDER_ID: str = "you-com"
    ALIAS: str = "youcom"
    BASE_URL: str = "https://api.you.com/v1"
    SERVICE_KINDS: list[str] = ["webSearch"]


class YoucomMetadata(BaseMetadata):
    """You.com UI display metadata."""

    name: str = "You.com"
    color: str = "#4A90D9"
    textIcon: str = "YC"
