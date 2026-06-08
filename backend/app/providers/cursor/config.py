"""Cursor IDE provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CursorConfig(BaseProviderConfig):
    """Cursor IDE provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cursor IDE"
    PROVIDER_ID: str = "cursor"
    ALIAS: str = "cu"
    BASE_URL: str = "https://api.cursor.sh"
    SERVICE_KINDS: list[str] = []
    CUSTOM_MODAL: str = "cursor"


class CursorMetadata(BaseMetadata):
    """Cursor IDE UI display metadata."""

    name: str = "Cursor IDE"
    color: str = "#00D4AA"
    textIcon: str = "CU"
    icon: str = "PenLine"
    website: str = "https://cursor.com"
    notice: dict | None = {"signupUrl": "https://cursor.com"}
