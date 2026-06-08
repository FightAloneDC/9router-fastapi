"""Fal.ai provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class FalAiConfig(BaseProviderConfig):
    """Fal.ai provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Fal.ai"
    PROVIDER_ID: str = "fal-ai"
    ALIAS: str = "fal"
    BASE_URL: str = "https://api.fal.ai/v1"
    SERVICE_KINDS: list[str] = ["image"]


class FalAiMetadata(BaseMetadata):
    """Fal.ai UI display metadata."""

    name: str = "Fal.ai"
    color: str = "#2563EB"
    textIcon: str = "FL"
    icon: str = "Image"
    website: str = "https://fal.ai"
    notice: dict | None = {"apiKeyUrl": "https://fal.ai/dashboard/keys"}
