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

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "nvidia/nv-embedqa-e5-v5": "embedding",
        "Qwen/Qwen3-Embedding-8B": "embedding",
        "fastpitch": "tts",
        "tacotron2": "tts",
    }


class NvidiaMetadata(BaseMetadata):
    """NVIDIA NIM UI display metadata."""

    name: str = "NVIDIA NIM"
    color: str = "#76B900"
    textIcon: str = "NV"
    icon: str = "Cpu"
    website: str = "https://developer.nvidia.com/nim"
    notice: dict | None = {"text": "Free access for NVIDIA Developer Program members.", "apiKeyUrl": "https://build.nvidia.com/settings/api-keys"}
