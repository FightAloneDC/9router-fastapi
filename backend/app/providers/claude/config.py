"""Claude Code provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class ClaudeConfig(BaseProviderConfig):
    """Claude Code provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Claude Code"
    PROVIDER_ID: str = "claude"
    ALIAS: str = "cc"
    BASE_URL: str = "https://api.anthropic.com"
    SERVICE_KINDS: list[str] = []
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."


class ClaudeMetadata(BaseMetadata):
    """Claude Code UI display metadata."""

    name: str = "Claude Code"
    color: str = "#D97757"
    textIcon: str = "CC"
    icon: str = "Bot"
    website: str = "https://claude.ai"
    notice: dict | None = {"signupUrl": "https://claude.ai"}
