"""Grok CLI (Grok Build) provider definition.

OAuth device-code auth via auth.x.ai, inference on
cli-chat-proxy.grok.com (OpenAI Responses API upstream).
"""

from app.providers.base import BaseMetadata, BaseProviderConfig
from app.providers.grok_cli.constants import (
    GROK_CLI_BASE_URL,
    GROK_CLI_CLIENT_IDENTIFIER,
    GROK_CLI_TOKEN_AUTH,
    GROK_CLI_USER_AGENT,
    GROK_CLI_VERSION,
)


class GrokCliConfig(BaseProviderConfig):
    """Grok CLI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Grok CLI (Grok Build)"
    PROVIDER_ID: str = "grok-cli"
    ALIAS: str = "gcli"
    BASE_URL: str = GROK_CLI_BASE_URL
    SERVICE_KINDS: list[str] = ["llm"]

    # ── Connection defaults ─────────────────────────────────────────────
    # Upstream speaks the OpenAI Responses API, not Chat Completions.
    FORMAT: str = "openai-responses"
    THINKING_CONFIG: dict | None = {
        "options": ["low", "medium", "high", "xhigh"],
        "defaultMode": "high",
    }
    # Accepts bulk JSON account import (grok-farm-modular export)
    SUPPORTS_BULK_IMPORT: bool = True
    SYNC_DISABLED_WITH_MODEL_LIST: bool = True

    # ── Static client fingerprint headers ──────────────────────────────
    EXTRA_HEADERS: dict[str, str] = {
        "User-Agent": GROK_CLI_USER_AGENT,
        "x-grok-client-identifier": GROK_CLI_CLIENT_IDENTIFIER,
        "x-grok-client-version": GROK_CLI_VERSION,
        "x-xai-token-auth": GROK_CLI_TOKEN_AUTH,
        "x-grok-client-mode": "headless",
    }


class GrokCliMetadata(BaseMetadata):
    """Grok CLI UI display metadata."""

    name: str = "Grok CLI (Grok Build)"
    color: str = "#1DA1F2"
    textIcon: str = "GC"
    icon: str = "Sparkles"
    website: str = "https://x.ai"
    notice: dict | None = {
        "text": (
            "Sign in with your xAI / Grok account via device code. "
            "Uses Grok Build subscription credits "
            "(cli-chat-proxy.grok.com)."
        ),
        "signupUrl": "https://grok.com/supergrok",
    }
