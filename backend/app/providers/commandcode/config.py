"""Command Code provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.

Sources (retrieved 2026-08-28):
- https://commandcode.ai/docs/provider
- https://commandcode.ai/docs/resources/usage-limits
"""

from app.providers.base import BaseMetadata, BaseProviderConfig

# Upstream catalog ids that require POST /messages (Anthropic shape).
CLAUDE_MODEL_PREFIX: str = "claude-"

# Studio tiers with no POST /provider/v1/* (403 upgrade_required).
PLANS_WITHOUT_PROVIDER_API: frozenset[str] = frozenset({"go"})


class CommandcodeConfig(BaseProviderConfig):
    """Command Code provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Command Code"
    PROVIDER_ID: str = "commandcode"
    ALIAS: str = "cmc"
    BASE_URL: str = "https://api.commandcode.ai/provider/v1"
    SERVICE_KINDS: list[str] = ["llm"]
    CATEGORY: str = "freeTier"
    MODEL_CATALOG_TABLE: bool = True

    # Studio subscription tiers (all are monthly subscribe plans on
    # commandcode.ai — NOT 9Router free/payg/subscribe tags).
    # Values: monthly / window_5h / weekly credit caps (USD, docs).
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "go": {"monthly": 10, "window_5h": 3, "weekly": 6},
        "goat": {"monthly": 70, "window_5h": 14, "weekly": 35},
        "pro": {"monthly": 80, "window_5h": 16, "weekly": 40},
        "max_10x": {"monthly": 150, "window_5h": 45, "weekly": 90},
        "max_20x": {"monthly": 300, "window_5h": 90, "weekly": 180},
        "team_pro": {"monthly": 40, "window_5h": 12, "weekly": 24},
        "provider": {},
    }

    # Alias → canonical RATE_LIMITS key (typos / shorthand only).
    STUDIO_PLAN_ALIASES: dict[str, str] = {
        "max10": "max_10x",
        "max20": "max_20x",
        "team": "team_pro",
    }

    # Catalog → connection row studio-plan selector (subscribe tiers).
    STUDIO_PLAN_OPTIONS: list[dict[str, str]] = [
        {"id": "go", "label": "Go ($1/mo, no Provider API)"},
        {"id": "goat", "label": "GOAT ($10/mo)"},
        {"id": "pro", "label": "Pro ($20/mo)"},
        {"id": "max_10x", "label": "Max 10x ($100/mo)"},
        {"id": "max_20x", "label": "Max 20x ($200/mo)"},
        {"id": "team_pro", "label": "Team Pro ($40/mo)"},
        {"id": "provider", "label": "Provider ($15/mo PAYG)"},
    ]


def normalize_studio_plan(value: str | None) -> str | None:
    """Return a canonical Studio subscribe-plan id, or None if blank."""
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    cfg = CommandcodeConfig()
    mapped = cfg.STUDIO_PLAN_ALIASES.get(raw, raw)
    if mapped in cfg.RATE_LIMITS:
        return mapped
    return None


class CommandcodeMetadata(BaseMetadata):
    """Command Code UI display metadata."""

    name: str = "Command Code"
    color: str = "#000000"
    textIcon: str = "CC"
    icon: str = "Bot"
    website: str = "https://commandcode.ai"
    notice: dict | None = {
        "text": (
            "Pick your Studio tier per connection (studioPlan). "
            "Go ($1/mo) is Studio-only — Provider API returns 403 "
            "upgrade_required; use GOAT or higher for API keys here. "
            "Provider tier is PAYG ($15/mo). Claude models use "
            "/messages; others /chat/completions."
        ),
        "apiKeyUrl": "https://commandcode.ai/settings/keys",
    }
