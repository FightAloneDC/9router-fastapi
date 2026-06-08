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

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "openai/whisper-large-v3": "stt",
        "openai/whisper-small": "stt",
        "whisper-large-v3": "stt",
        "whisper-large-v3-turbo": "stt",
        "distil-whisper-large-v3-en": "stt",
        "whisper-large": "stt",
        "tts_models/en/ljspeech/tacotron2-DDC": "tts",
    }


class HuggingfaceMetadata(BaseMetadata):
    """Hugging Face UI display metadata."""

    name: str = "Hugging Face"
    color: str = "#FFD21E"
    textIcon: str = "HF"
    icon: str = "Box"
    website: str = "https://huggingface.co"
    notice: dict | None = {"apiKeyUrl": "https://huggingface.co/settings/tokens"}
