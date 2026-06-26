"""OpenCode Free provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class OpencodeConfig(BaseProviderConfig):
    """OpenCode Free provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "OpenCode Free"
    PROVIDER_ID: str = "opencode"
    ALIAS: str = "oc"
    BASE_URL: str = "https://opencode.ai"
    SERVICE_KINDS: list[str] = ["llm"]
    CATEGORY: str = "free"
    NO_AUTH: bool = True
    MODELS_FETCHER: dict | None = {"url": "https://opencode.ai/zen/v1/models", "type": "opencode-free"}


class OpencodeMetadata(BaseMetadata):
    """OpenCode Free UI display metadata."""

    name: str = "OpenCode Free"
    color: str = "#E87040"
    textIcon: str = "OC"
    icon: str = "Terminal"
    website: str = "https://opencode.ai"
    notice: dict | None = {
        "text": "Free AI models via OpenCode CLI. No API key required."
    }
