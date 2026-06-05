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


class OpenaiMetadata(BaseMetadata):
    """OpenAI UI display metadata."""

    name: str = "OpenAI"
    color: str = "#10A37F"
    textIcon: str = "OA"
