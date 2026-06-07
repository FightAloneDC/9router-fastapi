"""OpenAI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OpenaiConfig(BaseProviderConfig):
    """OpenAI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenAI"
    PROVIDER_ID: str = "openai"
    ALIAS: str = "openai"
    BASE_URL: str = "https://api.openai.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"]

    # ── Model type overrides ────────────────────────────────────────────
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "text-embedding-3-small": "embedding",
        "text-embedding-3-large": "embedding",
        "text-embedding-ada-002": "embedding",
        "whisper-1": "stt",
        "gpt-4o-transcribe": "stt",
        "gpt-4o-mini-transcribe": "stt",
        "tts-1": "tts",
        "tts-1-hd": "tts",
        "gpt-4o-mini-tts": "tts",
        "dall-e-3": "image",
        "dall-e-2": "image",
    }


class OpenaiMetadata(BaseMetadata):
    """OpenAI UI display metadata."""

    name: str = "OpenAI"
    color: str = "#10A37F"
    textIcon: str = "OA"
