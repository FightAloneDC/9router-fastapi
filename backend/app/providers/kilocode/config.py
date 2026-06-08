"""Kilocode provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class KilocodeConfig(BaseProviderConfig):
    PROVIDER_NAME: str = "Kilo Code"
    PROVIDER_ID: str = "kilocode"
    ALIAS: str = "kilo"
    BASE_URL: str = "https://api.kilo.ai"
    SERVICE_KINDS: list[str] = ["llm"]


class KilocodeMetadata(BaseMetadata):
    name: str = "Kilo Code"
    color: str = "#FF6B35"
    textIcon: str = "KC"
