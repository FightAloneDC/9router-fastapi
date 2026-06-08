"""OpenAI Codex provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class CodexConfig(BaseProviderConfig):
    """OpenAI Codex provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenAI Codex"
    PROVIDER_ID: str = "codex"
    ALIAS: str = "cx"
    BASE_URL: str = "https://chatgpt.com"
    SERVICE_KINDS: list[str] = ["llm", "image"]
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."
    THINKING_CONFIG: dict | None = {"options": ["auto", "none", "low", "medium", "high"], "defaultMode": "auto"}
    REQUIRES_PROXY: bool = True


class CodexMetadata(BaseMetadata):
    """OpenAI Codex UI display metadata."""

    name: str = "OpenAI Codex"
    color: str = "#3B82F6"
    textIcon: str = "CX"
    icon: str = "Code"
    website: str = "https://chatgpt.com/codex"
    notice: dict | None = {"signupUrl": "https://chatgpt.com/codex"}
