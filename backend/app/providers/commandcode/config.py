"""Command Code provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CommandcodeConfig(BaseProviderConfig):
    """Command Code provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Command Code"
    PROVIDER_ID: str = "commandcode"
    ALIAS: str = "cmc"
    BASE_URL: str = "https://api.commandcode.ai/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class CommandcodeMetadata(BaseMetadata):
    """Command Code UI display metadata."""

    name: str = "Command Code"
    color: str = "#000000"
    textIcon: str = "CC"
    icon: str = "Bot"
    website: str = "https://commandcode.ai"
    notice: dict | None = {"apiKeyUrl": "https://commandcode.ai/studio"}
