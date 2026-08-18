"""Morph provider definition.

OpenAI-compatible provider for Morph LLM.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class MorphConfig(BaseProviderConfig):
    """Morph provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Morph"
    PROVIDER_ID: str = "morph"
    ALIAS: str = "mo"
    BASE_URL: str = "https://api.morphllm.com/v1"
    SERVICE_KINDS: list[str] = ["llm"]
    MODEL_CATALOG_TABLE: bool = True
    # Official tiers on /pricing (retrieved 2026-08-18):
    # free — 200 requests / month
    # payg — credits from $10, "practically no rate limits"
    # subscribe (Scale $200/mo) — same: no published RPM/RPD
    # Dedicated endpoints are out of scope (not listed).
    # `calls` = requests per calendar month, not RPD.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free": {"calls": 200},
        "payg": {},
        "subscribe": {},
    }


class MorphMetadata(BaseMetadata):
    """Morph UI display metadata."""

    name: str = "Morph"
    color: str = "#6366F1"
    textIcon: str = "MO"
    icon: str = "/providers/morph.png"
    website: str = "https://www.morphllm.com"
    notice: dict | None = {
        "text": (
            "Free: 200 requests/month. PAYG and Scale "
            "(subscribe): practically no rate limits "
            "(morphllm.com/pricing). Dedicated endpoints "
            "are not listed here."
        ),
        "apiKeyUrl": "https://www.morphllm.com/dashboard/api-keys",
    }
