"""Gemini CLI provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GeminiCliConfig(BaseProviderConfig):
    """Gemini CLI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Gemini CLI"
    PROVIDER_ID: str = "gemini-cli"
    ALIAS: str = "gc"
    BASE_URL: str = "https://generativelanguage.googleapis.com"
    SERVICE_KINDS: list[str] = []
    CATEGORY: str = "free"
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."


class GeminiCliMetadata(BaseMetadata):
    """Gemini CLI UI display metadata."""

    name: str = "Gemini CLI"
    color: str = "#4285F4"
    textIcon: str = "GC"
    icon: str = "Terminal"
    website: str = "https://github.com/google-gemini/gemini-cli"
    notice: dict | None = {"signupUrl": "https://github.com/google-gemini/gemini-cli"}
