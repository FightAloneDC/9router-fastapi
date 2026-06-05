"""Hugging Face provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class HuggingfaceConfig(BaseProviderConfig):
    """Hugging Face provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Hugging Face"
    PROVIDER_ID: str = "huggingface"
    ALIAS: str = "hf"
    BASE_URL: str = "https://api-inference.huggingface.co"
    SERVICE_KINDS: list[str] = ["image", "imageToText", "stt", "tts"]


class HuggingfaceMetadata(BaseMetadata):
    """Hugging Face UI display metadata."""

    name: str = "Hugging Face"
    color: str = "#FFD21E"
    textIcon: str = "HF"
