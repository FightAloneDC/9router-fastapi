"""Local Device provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class LocalDeviceConfig(BaseProviderConfig):
    """Local Device provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Local Device"
    PROVIDER_ID: str = "local-device"
    ALIAS: str = "local"
    BASE_URL: str = "http://localhost"
    SERVICE_KINDS: list[str] = ["tts"]
    AUTH_HEADER: str = ""
    AUTH_PREFIX: str = ""


class LocalDeviceMetadata(BaseMetadata):
    """Local Device UI display metadata."""

    name: str = "Local Device"
    color: str = "#6B7280"
    textIcon: str = "LD"
