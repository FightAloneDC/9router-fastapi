"""OpenCode Go provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OpencodeGoConfig(BaseProviderConfig):
    """OpenCode Go provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenCode Go"
    PROVIDER_ID: str = "opencode-go"
    ALIAS: str = "ocg"
    BASE_URL: str = "https://opencode.ai/api/v1"
    SERVICE_KINDS: list[str] = ["llm"]


class OpencodeGoMetadata(BaseMetadata):
    """OpenCode Go UI display metadata."""

    name: str = "OpenCode Go"
    color: str = "#E87040"
    textIcon: str = "OC"
    icon: str = "Terminal"
    website: str = "https://opencode.ai/auth"
    notice: dict | None = {"text": "OpenCode Go subscription: $5/mo (then $10/mo). Access to Kimi, GLM, Qwen, MiMo, MiniMax models.", "apiKeyUrl": "https://opencode.ai/auth"}
