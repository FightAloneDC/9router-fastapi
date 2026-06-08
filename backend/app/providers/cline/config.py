"""Cline provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ClineConfig(BaseProviderConfig):
    """Cline provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cline"
    PROVIDER_ID: str = "cline"
    ALIAS: str = "cl"
    BASE_URL: str = "https://api.cline.bot"
    SERVICE_KINDS: list[str] = []


class ClineMetadata(BaseMetadata):
    """Cline UI display metadata."""

    name: str = "Cline"
    color: str = "#5B9BD5"
    textIcon: str = "CL"
    icon: str = "Bot"
    website: str = "https://cline.bot"
    notice: dict | None = {"signupUrl": "https://cline.bot"}
