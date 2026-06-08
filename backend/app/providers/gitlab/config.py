"""GitLab provider definition."""

from app.providers.base import BaseMetadata, BaseProviderConfig


class GitlabConfig(BaseProviderConfig):
    """GitLab provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "GitLab"
    PROVIDER_ID: str = "gitlab"
    ALIAS: str = "gl"
    BASE_URL: str = "https://gitlab.com"
    SERVICE_KINDS: list[str] = []
    CUSTOM_MODAL: str = "gitlab"


class GitlabMetadata(BaseMetadata):
    """GitLab UI display metadata."""

    name: str = "GitLab"
    color: str = "#FC6D26"
    textIcon: str = "GL"
    icon: str = "Code"
    website: str = "https://gitlab.com"
    notice: dict | None = {"signupUrl": "https://gitlab.com"}
