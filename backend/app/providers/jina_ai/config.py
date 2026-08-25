"""Jina AI provider definition.

Runtime secrets / accountType live on ProviderConnection.data.

One provider, one API key, multiple service kinds and hosts
(api.jina.ai / s.jina.ai / r.jina.ai).

Static constants for this provider live **here** (hosts, default
models, WEB_CATALOG, RETURN_FORMAT_MAP, UI_TO_DOCS_PLAN,
RATE_LIMITS, …). handler / models / quota must read these fields —
do not re-declare module-level maps elsewhere (audit / PS).

Config class attributes are public API (no leading `_`). Private
helpers stay inside handler/models/quota with `_` only when they
are not imported elsewhere.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class JinaAiConfig(BaseProviderConfig):
    """Jina AI provider configuration."""

    PROVIDER_NAME: str = "Jina AI"
    PROVIDER_ID: str = "jina-ai"
    ALIAS: str = "jina"
    BASE_URL: str = "https://api.jina.ai/v1"
    # Search + Reader hosts (same key; not BASE_URL).
    SEARCH_BASE_URL: str = "https://s.jina.ai"
    READER_BASE_URL: str = "https://r.jina.ai"
    SERVICE_KINDS: list[str] = [
        "embedding",
        "rerank",
        "webSearch",
        "webFetch",
    ]
    MODEL_CATALOG_TABLE: bool = True
    # Mistaken split providers (same key) → this id.
    LEGACY_IDS: list[str] = [
        "jina-search",
        "jina-reader",
        "jinas",
        "jinar",
    ]
    # docs.jina.ai requires Accept: application/json on JSON APIs
    EXTRA_HEADERS: dict[str, str] = {
        "Accept": "application/json",
    }
    # Defaults for validate ping + missing request model.
    DEFAULT_EMBEDDING_MODEL: str = "jina-embeddings-v3"
    DEFAULT_RERANK_MODEL: str = "jina-reranker-v3.5"

    # Catalog → Provider Detail RateLimitsNote.
    # free/premium rows = embed+rerank (docs) + operator tokens.
    # search/reader rows = docs RPM only (no published TPM).
    # free tokens = operator: 2026-08-25 (shared key grant).
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "free": {
            "rpm": 500,
            "tpm": 1_000_000,
            "tokens": 10_000_000,
        },
        "premium": {
            "rpm": 2000,
            "tpm": 5_000_000,
        },
        "search free": {"rpm": 100},
        "search premium": {"rpm": 1000},
        "reader free": {"rpm": 500},
        "reader premium": {"rpm": 5000},
    }

    MODEL_TYPE_OVERRIDES: dict[str, str] = {
        "jina-clip-v1": "embedding",
        "jina-clip-v2": "embedding",
        "jina-colbert-v1-en": "rerank",
        "jina-colbert-v2": "rerank",
        "search": "webSearch",
        "reader": "webFetch",
    }

    # Synthetic catalog rows (s/r have no /models list).
    WEB_CATALOG: list[dict[str, str]] = [
        {"id": "search", "name": "search", "type": "webSearch"},
        {"id": "reader", "name": "reader", "type": "webFetch"},
    ]

    # Unified format → r.jina.ai X-Return-Format.
    RETURN_FORMAT_MAP: dict[str, str] = {
        "markdown": "markdown",
        "text": "text",
        "html": "html",
    }

    # UI ConnectionRow accountType → docs free|premium.
    UI_TO_DOCS_PLAN: dict[str, str] = {
        "free": "free",
        "premium": "premium",
        "payg": "premium",
        "subscribe": "premium",
    }


class JinaAiMetadata(BaseMetadata):
    """Jina AI UI display metadata."""

    name: str = "Jina AI"
    color: str = "#2563EB"
    textIcon: str = "JA"
    icon: str = "Layers"
    website: str = "https://jina.ai"
    notice: dict | None = {
        "text": (
            "One API key for embed, rerank, search, and reader. "
            "10M free tokens on free/browser keys "
            "(operator note)."
        ),
        "apiKeyUrl": "https://jina.ai/?sui=apikey",
    }
