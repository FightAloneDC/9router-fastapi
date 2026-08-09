"""Keelcode provider definition.

Hosted coding-agent inference API (Anthropic Messages compatible).
Runtime tokens come from ProviderConnection.data (OAuth device flow).
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class KeelcodeConfig(BaseProviderConfig):
    """Keelcode provider configuration."""

    PROVIDER_NAME: str = "Keelcode"
    PROVIDER_ID: str = "keelcode"
    ALIAS: str = "keel"
    BASE_URL: str = "https://api.keelcode.ai/v1"
    FORMAT: str = "claude"
    SERVICE_KINDS: list[str] = ["llm"]
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {
        "anthropic-version": "2023-06-01",
    }
    CATEGORY: str = "oauth"


class KeelcodeMetadata(BaseMetadata):
    """Keelcode UI display metadata."""

    name: str = "Keelcode"
    color: str = "#101114"
    textIcon: str = "KC"
    icon: str = "Code"
    website: str = "https://keelcode.ai"
    notice: dict | None = {
        "signupUrl": "https://keelcode.ai",
    }
    authHint: str = (
        "Sign in with device approval (keelcode-cli). "
        "API keys are issued manually by Keelcode."
    )
