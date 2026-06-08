"""GitHub Copilot provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GithubConfig(BaseProviderConfig):
    """GitHub Copilot provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GitHub Copilot"
    PROVIDER_ID: str = "github"
    ALIAS: str = "gh"
    BASE_URL: str = "https://api.githubcopilot.com"
    SERVICE_KINDS: list[str] = ["llm", "embedding"]
    DEPRECATED: bool = True
    DEPRECATION_NOTICE: str = "Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk."


class GithubMetadata(BaseMetadata):
    """GitHub Copilot UI display metadata."""

    name: str = "GitHub Copilot"
    color: str = "#333333"
    textIcon: str = "GH"
    icon: str = "Code"
    website: str = "https://github.com/features/copilot"
    notice: dict | None = {"signupUrl": "https://github.com/features/copilot"}
