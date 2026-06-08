"""Perplexity Web (Pro/Max) provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class PerplexityWebConfig(BaseProviderConfig):
    """Perplexity Web (Pro/Max) provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Perplexity Web (Pro/Max)"
    PROVIDER_ID: str = "perplexity-web"
    ALIAS: str = "pw"
    BASE_URL: str = "https://www.perplexity.ai"
    SERVICE_KINDS: list[str] = ["llm"]


class PerplexityWebMetadata(BaseMetadata):
    """Perplexity Web (Pro/Max) UI display metadata."""

    name: str = "Perplexity Web (Pro/Max)"
    color: str = "#20808D"
    textIcon: str = "PW"
    icon: str = "Search"
    website: str = "https://www.perplexity.ai"
    notice: dict | None = {"authHint": "Paste your __Secure-next-auth.session-token cookie value from perplexity.ai"}
