"""NVIDIA NIM provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class NvidiaConfig(BaseProviderConfig):
    """NVIDIA NIM provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "NVIDIA NIM"
    PROVIDER_ID: str = "nvidia"
    ALIAS: str = "nvidia"
    BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "tts", "embedding"]


class NvidiaMetadata(BaseMetadata):
    """NVIDIA NIM UI display metadata."""

    name: str = "NVIDIA NIM"
    color: str = "#76B900"
    textIcon: str = "NV"
