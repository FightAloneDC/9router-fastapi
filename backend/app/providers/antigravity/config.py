"""Antigravity provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AntigravityConfig(BaseProviderConfig):
    """Antigravity provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Antigravity"
    PROVIDER_ID: str = "antigravity"
    ALIAS: str = "ag"
    BASE_URL: str = "https://antigravity.google"
    SERVICE_KINDS: list[str] = []
    HIDDEN: bool = True
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "AG is designed exclusively for Antigravity IDE."


class AntigravityMetadata(BaseMetadata):
    """Antigravity UI display metadata."""

    name: str = "Antigravity"
    color: str = "#F59E0B"
    textIcon: str = "AG"
    icon: str = "Rocket"
    website: str = "https://antigravity.google"
    notice: dict | None = {"signupUrl": "https://antigravity.google"}
