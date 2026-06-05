"""DeepSeek provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class DeepseekConfig(BaseProviderConfig):
    """DeepSeek provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "DeepSeek"
    PROVIDER_ID: str = "deepseek"
    ALIAS: str = "ds"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.deepseek.com"
    SERVICE_KINDS: list[str] = ["llm"]


class DeepseekMetadata(BaseMetadata):
    """DeepSeek UI display metadata."""

    name: str = "DeepSeek"
    color: str = "#0066FF"
    textIcon: str = "DS"
