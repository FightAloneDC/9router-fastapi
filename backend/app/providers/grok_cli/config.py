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
    # Fetch/set/clear → provider_models (not connection data.models).
    MODEL_CATALOG_TABLE: bool = True
    # Free daily token cap is account-random: 1M or 500K
    # (operator 2026-08). Headers often claim 1M; 429 body may
    # show 500K. requests=21 from X-Ratelimit-Limit-Requests.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free/1m": {"tpd": 1_000_000, "requests": 21},
        "free/500k": {"tpd": 500_000, "requests": 21},
    }

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
            "Sign in via device code (auth.x.ai). Free daily "
            "tokens are 1M or 500K at random per account "
            "(Limit-Requests often 21). Used = local "
            "usage_history; remaining headers are not trusted. "
            "cli-chat-proxy.grok.com Responses API."
        ),
        "signupUrl": "https://grok.com/supergrok",
    }
