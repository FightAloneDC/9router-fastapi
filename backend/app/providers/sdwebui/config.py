"""Stable Diffusion WebUI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class SdwebuiConfig(BaseProviderConfig):
    """Stable Diffusion WebUI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Stable Diffusion WebUI"
    PROVIDER_ID: str = "sdwebui"
    ALIAS: str = "sd"
    BASE_URL: str = "http://localhost:7860"
    SERVICE_KINDS: list[str] = ["image"]


class SdwebuiMetadata(BaseMetadata):
    """Stable Diffusion WebUI UI display metadata."""

    name: str = "Stable Diffusion WebUI"
    color: str = "#A855F7"
    textIcon: str = "SD"
