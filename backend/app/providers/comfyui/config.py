"""ComfyUI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ComfyuiConfig(BaseProviderConfig):
    """ComfyUI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "ComfyUI"
    PROVIDER_ID: str = "comfyui"
    ALIAS: str = "cfui"
    BASE_URL: str = "http://localhost:8188"
    SERVICE_KINDS: list[str] = ["image"]


class ComfyuiMetadata(BaseMetadata):
    """ComfyUI UI display metadata."""

    name: str = "ComfyUI"
    color: str = "#EC4899"
    textIcon: str = "CU"
