"""Fireworks provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class FireworksConfig(BaseProviderConfig):
    """Fireworks provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Fireworks"
    PROVIDER_ID: str = "fireworks"
    ALIAS: str = "fw"
    BASE_URL: str = "https://api.fireworks.ai/inference/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]


class FireworksMetadata(BaseMetadata):
    """Fireworks UI display metadata."""

    name: str = "Fireworks"
    color: str = "#FF4F00"
    textIcon: str = "FW"
    icon: str = "Flame"
    website: str = "https://fireworks.ai"
    notice: dict | None = {"apiKeyUrl": "https://fireworks.ai/account/api-keys"}
