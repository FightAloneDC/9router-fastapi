"""Voyage AI provider definition.

Static provider characteristics — runtime data (API keys, custom baseUrl)
come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class VoyageAiConfig(BaseProviderConfig):
    """Voyage AI provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Voyage AI"
    PROVIDER_ID: str = "voyage-ai"
    ALIAS: str = "voyage"
    BASE_URL: str = "https://api.voyageai.com/v1"
    SERVICE_KINDS: list[str] = ["embedding", "rerank"]
    MODEL_CATALOG_TABLE: bool = True

    # Tier 1 org RPM/TPM from
    # https://docs.voyageai.com/docs/rate-limits.md (2026-08-25).
    # Tier 2 = 2x, tier 3 = 3x; this table is tier 1 only.
    # voyage-3 / voyage-3-lite are not in that table.
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "voyage-3-large": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-context-3": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-code-3": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-large-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-large-2-instruct": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-finance-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-law-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-multilingual-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-code-2": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-4": {"rpm": 2000, "tpm": 8_000_000},
        "voyage-code-4": {"rpm": 2000, "tpm": 8_000_000},
        "voyage-3.5": {"rpm": 2000, "tpm": 8_000_000},
        "voyage-4-large": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-context-4": {"rpm": 2000, "tpm": 3_000_000},
        "voyage-4-lite": {"rpm": 2000, "tpm": 16_000_000},
        "voyage-3.5-lite": {"rpm": 2000, "tpm": 16_000_000},
        "voyage-multimodal-3.5": {"rpm": 2000, "tpm": 2_000_000},
        "voyage-multimodal-3": {"rpm": 2000, "tpm": 2_000_000},
        "rerank-2.5-lite": {"rpm": 2000, "tpm": 4_000_000},
        "rerank-2-lite": {"rpm": 2000, "tpm": 4_000_000},
        "rerank-lite-1": {"rpm": 2000, "tpm": 4_000_000},
        "rerank-2.5": {"rpm": 2000, "tpm": 2_000_000},
        "rerank-2": {"rpm": 2000, "tpm": 2_000_000},
        "rerank-1": {"rpm": 2000, "tpm": 2_000_000},
    }

    # Lifetime free-token grant per account from
    # https://docs.voyageai.com/docs/pricing.md (2026-08-25).
    # Numbers come from the current-model tables and the current
    # reranker prose. Older models have none. Batch API does not
    # consume these. 150B multimodal pixels are not tracked here.
    FREE_TOKENS: dict[str, int] = {
        "voyage-4-large": 200_000_000,
        "voyage-4": 200_000_000,
        "voyage-4-lite": 200_000_000,
        "voyage-context-4": 200_000_000,
        "voyage-code-4": 200_000_000,
        "voyage-finance-2": 50_000_000,
        "voyage-law-2": 50_000_000,
        "voyage-code-2": 50_000_000,
        "voyage-multimodal-3.5": 200_000_000,
        "voyage-multimodal-3": 200_000_000,
        "rerank-2.5": 200_000_000,
        "rerank-2.5-lite": 200_000_000,
        "rerank-2": 200_000_000,
        "rerank-2-lite": 200_000_000,
    }

    # ── Model type overrides ────────────────────────────────────────────
    # Catalog source of truth. models.HARDCODED_MODELS is built
    # from this map.
    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "voyage-4-large": "embedding",
        "voyage-4": "embedding",
        "voyage-4-lite": "embedding",
        "voyage-code-4": "embedding",
        "voyage-finance-2": "embedding",
        "voyage-law-2": "embedding",
        "voyage-code-2": "embedding",
        "voyage-3-large": "embedding",
        "voyage-3.5": "embedding",
        "voyage-3.5-lite": "embedding",
        "voyage-3": "embedding",
        "voyage-3-lite": "embedding",
        "voyage-code-3": "embedding",
        "voyage-multilingual-2": "embedding",
        "voyage-large-2-instruct": "embedding",
        "voyage-large-2": "embedding",
        "voyage-2": "embedding",
        "voyage-context-4": "embedding",
        "voyage-context-3": "embedding",
        "voyage-multimodal-3.5": "embedding",
        "voyage-multimodal-3": "embedding",
        "rerank-2.5": "rerank",
        "rerank-2.5-lite": "rerank",
        "rerank-2": "rerank",
        "rerank-2-lite": "rerank",
        "rerank-1": "rerank",
        "rerank-lite-1": "rerank",
    }


class VoyageAiMetadata(BaseMetadata):
    """Voyage AI UI display metadata."""

    name: str = "Voyage AI"
    color: str = "#FF6B6B"
    textIcon: str = "VY"
    icon: str = "Compass"
    website: str = "https://www.voyageai.com"
    notice: dict | None = {"apiKeyUrl": "https://dash.voyageai.com/api-keys"}
