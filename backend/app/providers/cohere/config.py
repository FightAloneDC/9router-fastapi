"""Cohere provider definition.

Static provider characteristics — runtime data (API keys, custom
baseUrl) come from ProviderConnection.data in the database.

RATE_LIMITS keys use exact catalog / upstream model ids (same
pattern as Groq and alims-intl), prefixed by accountType plan.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig

# Chat RPM from docs.cohere.com/docs/rate-limits mapped onto the
# dated ids present in provider_models for this install.
_CHAT_FREE_20: tuple[str, ...] = (
    "command-a-03-2025",
    "command-a-plus-05-2026",
    "command-a-reasoning-08-2025",
    "command-a-translate-08-2025",
    "command-a-vision-07-2025",
    "command-r-08-2024",
    "command-r-plus-08-2024",
    "command-r7b-12-2024",
    "command-r7b-arabic-02-2025",
    "north-mini-code-1-0",
)
# Production self-serve 500 RPM (docs). Newer A variants stay 20.
_CHAT_PAYG_500: tuple[str, ...] = (
    "command-a-03-2025",
    "command-r-08-2024",
    "command-r-plus-08-2024",
    "command-r7b-12-2024",
    "command-r7b-arabic-02-2025",
    "north-mini-code-1-0",
)
_CHAT_PAYG_20: tuple[str, ...] = (
    "command-a-plus-05-2026",
    "command-a-reasoning-08-2025",
    "command-a-translate-08-2025",
    "command-a-vision-07-2025",
)
_RERANK_IDS: tuple[str, ...] = (
    "rerank-english-v3.0",
    "rerank-multilingual-v3.0",
    "rerank-v3.5",
    "rerank-v4.0-fast",
    "rerank-v4.0-pro",
)
_EMBED_IDS: tuple[str, ...] = (
    "embed-english-light-v3.0",
    "embed-english-light-v3.0-image",
    "embed-english-v3.0",
    "embed-english-v3.0-image",
    "embed-multilingual-light-v3.0",
    "embed-multilingual-light-v3.0-image",
    "embed-multilingual-v3.0",
    "embed-multilingual-v3.0-image",
    "embed-v4.0",
)


def _build_rate_limits() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {
        "free/_monthly": {"calls": 1000},
    }
    for mid in _CHAT_FREE_20:
        out[f"free/{mid}"] = {"rpm": 20}
    for mid in _CHAT_PAYG_500:
        out[f"payg/{mid}"] = {"rpm": 500}
        out[f"subscribe/{mid}"] = {"rpm": 500}
    for mid in _CHAT_PAYG_20:
        out[f"payg/{mid}"] = {"rpm": 20}
        out[f"subscribe/{mid}"] = {"rpm": 20}
    for mid in _RERANK_IDS:
        out[f"free/{mid}"] = {"rpm": 10}
        out[f"payg/{mid}"] = {"rpm": 1000}
        out[f"subscribe/{mid}"] = {"rpm": 1000}
    for mid in _EMBED_IDS:
        out[f"free/{mid}"] = {"ipm": 2000}
        out[f"payg/{mid}"] = {"ipm": 2000}
        out[f"subscribe/{mid}"] = {"ipm": 2000}
    return out


class CohereConfig(BaseProviderConfig):
    """Cohere provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Cohere"
    PROVIDER_ID: str = "cohere"
    ALIAS: str = "co"
    BASE_URL: str = "https://api.cohere.com/compatibility/v1"
    SERVICE_KINDS: list[str] = ["llm", "embedding", "rerank"]
    CATEGORY: str = "freeTier"
    MODEL_CATALOG_TABLE: bool = True
    # Exact upstream ids from provider_models + docs RPM/IPM.
    # free = trial key; payg/subscribe = production.
    RATE_LIMITS: dict[str, dict[str, int]] = _build_rate_limits()


class CohereMetadata(BaseMetadata):
    """Cohere UI display metadata."""

    name: str = "Cohere"
    color: str = "#39594D"
    textIcon: str = "CO"
    icon: str = "Sparkles"
    website: str = "https://dashboard.cohere.com"
    notice: dict | None = {
        "text": (
            "Free (trial key): 20 RPM Chat per model, 1000 API "
            "calls/month. PAYG/Subscribe (production): 500 RPM "
            "on standard Command models; newer A variants stay "
            "at 20 RPM (contact Cohere sales)."
        ),
        "apiKeyUrl": "https://dashboard.cohere.com/api-keys",
    }
