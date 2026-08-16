"""Groq provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GroqConfig(BaseProviderConfig):
    """Groq provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Groq"
    PROVIDER_ID: str = "groq"
    ALIAS: str = "gq"
    BASE_URL: str = "https://api.groq.com/openai/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText", "stt"]
    MODEL_CATALOG_TABLE: bool = True
    # Developer-plan base from Groq docs (org-level, not IP).
    # Exact org caps: console.groq.com/settings/limits
    # rpm/rpd/tpm/tpd; whisper uses ash/asd instead of tokens.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "canopylabs/orpheus-arabic-saudi": {
            "rpm": 10, "rpd": 100, "tpm": 1200, "tpd": 3600,
        },
        "canopylabs/orpheus-v1-english": {
            "rpm": 10, "rpd": 100, "tpm": 1200, "tpd": 3600,
        },
        "groq/compound": {
            "rpm": 30, "rpd": 250, "tpm": 70000,
        },
        "groq/compound-mini": {
            "rpm": 30, "rpd": 250, "tpm": 70000,
        },
        "llama-3.1-8b-instant": {
            "rpm": 30, "rpd": 14400, "tpm": 6000, "tpd": 500000,
        },
        "llama-3.3-70b-versatile": {
            "rpm": 30, "rpd": 1000, "tpm": 12000, "tpd": 100000,
        },
        "meta-llama/llama-prompt-guard-2-22m": {
            "rpm": 30, "rpd": 14400, "tpm": 15000, "tpd": 500000,
        },
        "meta-llama/llama-prompt-guard-2-86m": {
            "rpm": 30, "rpd": 14400, "tpm": 15000, "tpd": 500000,
        },
        "openai/gpt-oss-120b": {
            "rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200000,
        },
        "openai/gpt-oss-20b": {
            "rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200000,
        },
        "openai/gpt-oss-safeguard-20b": {
            "rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200000,
        },
        "qwen/qwen3.6-27b": {
            "rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200000,
        },
        "whisper-large-v3": {
            "rpm": 20, "rpd": 2000, "ash": 7200, "asd": 28800,
        },
        "whisper-large-v3-turbo": {
            "rpm": 20, "rpd": 2000, "ash": 7200, "asd": 28800,
        },
    }


class GroqMetadata(BaseMetadata):
    """Groq UI display metadata."""

    name: str = "Groq"
    color: str = "#F55036"
    textIcon: str = "GQ"
    icon: str = "Zap"
    website: str = "https://console.groq.com"
    notice: dict | None = {"apiKeyUrl": "https://console.groq.com/keys"}
