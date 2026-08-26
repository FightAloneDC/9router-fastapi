"""DeepSeek provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class DeepseekConfig(BaseProviderConfig):
    """DeepSeek provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "DeepSeek"
    PROVIDER_ID: str = "deepseek"
    ALIAS: str = "ds"

    # ── Connection defaults ─────────────────────────────────────────────
    BASE_URL: str = "https://api.deepseek.com"
    SERVICE_KINDS: list[str] = ["llm"]
    MODEL_CATALOG_TABLE: bool = True
    CATEGORY: str = "freeTier"

    # Signup grant (operator 2026-08-26 + platform docs): new API
    # accounts receive ~5M tokens valid ~30 days from registration.
    # value_usd_cents is the marketed grant value (~$8.40) used to
    # render the granted-balance bar against GET /user/balance.
    # Concurrency caps: api-docs.deepseek.com/quick_start/rate_limit
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "signup_grant": {
            "tokens": 5_000_000,
            "days": 30,
            "value_usd_cents": 840,
        },
        "deepseek-v4-pro": {"concurrency": 500},
        "deepseek-v4-flash": {"concurrency": 2500},
        "deepseek-v4-flash-vision-exp": {
            "concurrency": 2500,
        },
    }


class DeepseekMetadata(BaseMetadata):
    """DeepSeek UI display metadata."""

    name: str = "DeepSeek"
    color: str = "#0066FF"
    textIcon: str = "DS"
    icon: str = "Sparkles"
    website: str = "https://platform.deepseek.com"
    notice: dict | None = {
        "apiKeyUrl": "https://platform.deepseek.com/api_keys",
        "text": (
            "New API accounts: ~5M token signup grant, valid "
            "~30 days from registration (no card required). "
            "Live balance: Quota Tracker / GET /user/balance. "
            "After grant expires, pay-as-you-go from topped-up "
            "balance."
        ),
    }
