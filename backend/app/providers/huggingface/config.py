"""Hugging Face provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from pydantic import BaseModel


class HuggingfaceConfig(BaseModel):
    """Hugging Face provider configuration template."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Hugging Face"
    PROVIDER_ID: str = "huggingface"
    ALIAS: str = "hf"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api-inference.huggingface.co"
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = ['image', 'imageToText', 'stt', 'tts']

    # ── Auth ────────────────────────────────────────────────────────────
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}

    # ── Runtime (from DB connection, not .env) ──────────────────────────
    API_KEY: str = ""


class HuggingfaceMetadata(BaseModel):
    """Hugging Face UI display metadata."""

    name: str = "Hugging Face"
    color: str = "#FFD21E"
    textIcon: str = "HF"
