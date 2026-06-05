"""Anthropic provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AnthropicConfig(BaseProviderConfig):
    """Anthropic provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Anthropic"
    PROVIDER_ID: str = "anthropic"
    ALIAS: str = "an"
    BASE_URL: str = "https://api.anthropic.com/v1"
    SERVICE_KINDS: list[str] = ["llm", "imageToText"]
    AUTH_HEADER: str = "x-api-key"
    AUTH_PREFIX: str = ""
    EXTRA_HEADERS: dict[str, str] = {"anthropic-version": "2023-06-01"}


class AnthropicMetadata(BaseMetadata):
    """Anthropic UI display metadata."""

    name: str = "Anthropic"
    color: str = "#D97757"
    textIcon: str = "AC"
