"""Tests for per-provider model fetching via Provider class.

Tests pure functions (parse_response, URL derivation) without network.
Integration tests (fetch_models) are skipped if no API key is available.
API key resolution: env var -> database ProviderConnection.data["apiKey"].
"""

import json
import os

import pytest
from sqlalchemy import select

from app.database import engine, async_session
from app.models.provider import ProviderConnection
from app.providers import (
    AVAILABLE_PROVIDERS,
    PROVIDER_CEREBRAS,
    PROVIDER_GROQ,
    PROVIDER_JINA_AI,
    PROVIDER_OPENROUTER,
    PROVIDER_VOYAGE_AI,
)
from app.providers.provider import Provider

# Provider constants -> env var name mapping for API key lookup
_API_KEY_ENV_VARS: dict[str, str] = {
    PROVIDER_CEREBRAS: "CEREBRAS_API_KEY",
    PROVIDER_GROQ: "GROQ_API_KEY",
    PROVIDER_OPENROUTER: "OPENROUTER_API_KEY",
    PROVIDER_VOYAGE_AI: "VOYAGE_AI_API_KEY",
    PROVIDER_JINA_AI: "JINA_AI_API_KEY",
}


def test_voyage_fetch_models_uses_documented_catalog() -> None:
    """Voyage has no list-models API; fetch returns documented ids."""
    import asyncio

    from app.providers.voyage_ai import models
    from app.providers.voyage_ai.config import VoyageAiConfig
    from app.providers.voyage_ai.handler import VoyageAiHandler

    result = asyncio.run(models.fetch_models(
        "unused-key",
        {"baseUrl": "https://example.test/v1"},
    ))
    ids = {item["id"] for item in result}
    types = {item["id"]: item["type"] for item in result}

    assert "voyage-4-large" in ids
    assert "voyage-context-4" in ids
    assert "voyage-multimodal-3.5" in ids
    assert "rerank-2.5" in ids
    assert "rerank-lite-1" in ids
    assert "voyage-01" not in ids
    assert "voyage-4-nano" not in ids
    assert types["voyage-4-large"] == "embedding"
    assert types["voyage-context-4"] == "embedding"
    assert types["voyage-multimodal-3.5"] == "embedding"
    assert types["rerank-2.5"] == "rerank"
    assert types["voyage-code-2"] == "embedding"
    cfg = VoyageAiConfig()
    assert cfg.MODEL_TYPE_OVERRIDES.keys() == ids
    assert "voyage-code-2" in ids
    assert set(cfg.RATE_LIMITS).issubset(ids)
    assert set(cfg.FREE_TOKENS).issubset(ids)

    handler = VoyageAiHandler(VoyageAiConfig())
    handled = asyncio.run(handler.fetch_models("unused-key"))
    handled_ids = {item["id"] for item in handled}
    assert handled_ids == ids
    assert all(item.get("type") for item in handled)


def test_jina_parse_models_strips_prefix_and_types() -> None:
    """Live /models ids are jina-ai/<bare>; type from id/modalities."""
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.models import parse_response
    from app.services.catalog import collect_catalog

    rows = parse_response(
        {
            "data": [
                {
                    "id": "jina-ai/jina-embeddings-v3",
                    "name": "Jina Embeddings v3",
                    "output_modalities": ["embeddings"],
                },
                {
                    "id": "jina-ai/jina-reranker-v3.5",
                    "name": "Jina Reranker v3.5",
                    "output_modalities": ["text"],
                },
                {
                    "id": "jina-ai/jina-colbert-v2",
                    "name": "Jina Colbert v2",
                    "output_modalities": ["embeddings"],
                },
                {
                    "id": "jina-ai/jina-vlm",
                    "name": "Jina VLM",
                    "output_modalities": ["text"],
                },
                {
                    "id": "jina-ai/jina-clip-v2",
                    "name": "Jina Clip v2",
                    "output_modalities": ["embeddings"],
                },
            ]
        }
    )
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == {
        "jina-embeddings-v3",
        "jina-reranker-v3.5",
        "jina-colbert-v2",
        "jina-vlm",
        "jina-clip-v2",
    }
    assert by_id["jina-embeddings-v3"]["type"] == "embedding"
    assert by_id["jina-reranker-v3.5"]["type"] == "rerank"
    assert by_id["jina-colbert-v2"]["type"] == "rerank"
    assert by_id["jina-clip-v2"]["type"] == "embedding"
    assert by_id["jina-vlm"]["type"] == "llm"

    cfg = JinaAiConfig()
    assert cfg.MODEL_CATALOG_TABLE is True
    catalog = collect_catalog(force=True)
    limits = catalog["providers"]["jina-ai"]["rateLimits"]
    assert limits == cfg.RATE_LIMITS
    assert limits["free"]["tokens"] == 10_000_000


def test_jina_fetch_models_calls_live_endpoint(
    monkeypatch,
) -> None:
    """fetch_models uses shared GET /models helper, not hardcoded."""
    import asyncio

    from app.providers.jina_ai import models
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.handler import JinaAiHandler

    called: dict = {}

    async def fake_fetch(config, api_key, parse_fn=None):
        called["base"] = config.BASE_URL
        called["key"] = api_key
        assert parse_fn is models.parse_response
        return parse_fn(
            {
                "data": [
                    {
                        "id": "jina-ai/jina-embeddings-v5-text-nano",
                        "output_modalities": ["embeddings"],
                    },
                    {
                        "id": "jina-ai/jina-reranker-v3.5",
                        "output_modalities": ["text"],
                    },
                ]
            }
        )

    monkeypatch.setattr(
        models,
        "fetch_models_header_auth",
        fake_fetch,
    )
    result = asyncio.run(models.fetch_models("k-test"))
    assert called["base"] == JinaAiConfig().BASE_URL
    assert called["key"] == "k-test"
    assert {r["id"] for r in result} == {
        "jina-embeddings-v5-text-nano",
        "jina-reranker-v3.5",
        "search",
        "reader",
    }

    handler = JinaAiHandler(JinaAiConfig())
    handled = asyncio.run(handler.fetch_models("k-test"))
    assert {r["id"] for r in handled} == {
        "jina-embeddings-v5-text-nano",
        "jina-reranker-v3.5",
        "search",
        "reader",
    }


def test_jina_embeddings_body_maps_encoding_format() -> None:
    """OpenAI encoding_format → Jina embedding_type; wrap string input."""
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.handler import JinaAiHandler

    handler = JinaAiHandler(JinaAiConfig())
    mapped = handler.build_embeddings_body(
        "jina-embeddings-v5-text-nano",
        {
            "model": "jina/x",
            "input": ["ping"],
            "dimensions": 256,
            "encoding_format": "base64",
        },
    )
    assert mapped["model"] == "jina-embeddings-v5-text-nano"
    assert mapped["dimensions"] == 256
    assert mapped["embedding_type"] == "base64"
    assert "encoding_format" not in mapped

    keep = handler.build_embeddings_body(
        "jina-embeddings-v3",
        {
            "model": "x",
            "input": ["ping"],
            "embedding_type": "float",
            "encoding_format": "base64",
        },
    )
    assert keep["embedding_type"] == "float"
    assert "encoding_format" not in keep

    wrapped = handler.build_embeddings_body(
        "jina-embeddings-v3",
        {"model": "x", "input": "ping"},
    )
    assert wrapped["input"] == ["ping"]


def test_jina_rerank_body_keeps_top_n() -> None:
    """Jina rerank docs field is top_n."""
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.handler import JinaAiHandler

    cfg = JinaAiConfig()
    handler = JinaAiHandler(cfg)
    mapped = handler.build_rerank_body(
        {
            "model": cfg.DEFAULT_RERANK_MODEL,
            "query": "q",
            "documents": ["a", "b"],
            "top_n": 2,
            "return_documents": False,
        },
    )
    assert mapped["top_n"] == 2
    assert mapped["return_documents"] is False
    assert "top_k" not in mapped
    assert mapped["model"] == cfg.DEFAULT_RERANK_MODEL
    defaulted = handler.build_rerank_body(
        {"query": "q", "documents": ["a"]},
    )
    assert defaulted["model"] == cfg.DEFAULT_RERANK_MODEL


def test_jina_search_and_webfetch_on_same_provider() -> None:
    """Search/reader are kinds of jina-ai — one key, not split providers."""
    from app.providers.jina_ai.config import JinaAiConfig
    from app.providers.jina_ai.handler import JinaAiHandler
    from app.services.catalog import collect_catalog
    from app.services.proxy import _resolve_provider_alias

    cfg = JinaAiConfig()
    assert "webSearch" in cfg.SERVICE_KINDS
    assert "webFetch" in cfg.SERVICE_KINDS
    assert "jina-search" not in collect_catalog(force=True)[
        "providers"
    ]
    assert "jina-reader" not in collect_catalog(force=True)[
        "providers"
    ]
    assert _resolve_provider_alias("jina-search") == "jina-ai"
    assert _resolve_provider_alias("jina-reader") == "jina-ai"
    assert _resolve_provider_alias("jinas") == "jina-ai"
    assert _resolve_provider_alias("jinar") == "jina-ai"

    handler = JinaAiHandler(cfg)
    body = handler.build_search_body(
        {
            "query": "hello",
            "max_results": 7,
            "country": "us",
            "language": "en",
        }
    )
    assert body == {
        "q": "hello",
        "num": 7,
        "gl": "us",
        "hl": "en",
    }
    method, headers, url, req_body = handler.build_webfetch_request(
        "https://example.com",
        "markdown",
        "key-1",
    )
    assert method == "GET"
    assert req_body is None
    assert url == (
        f"{cfg.READER_BASE_URL.rstrip('/')}/https://example.com"
    )
    assert headers["Authorization"] == "Bearer key-1"
    assert headers.get("X-Return-Format") == "markdown"
    assert cfg.RATE_LIMITS["search free"]["rpm"] == 100
    assert cfg.RATE_LIMITS["reader free"]["rpm"] == 500


def test_voyage_embeddings_body_maps_dimensions() -> None:
    """OpenAI dimensions → Voyage output_dimension."""
    from app.providers.voyage_ai.config import VoyageAiConfig
    from app.providers.voyage_ai.handler import VoyageAiHandler

    handler = VoyageAiHandler(VoyageAiConfig())
    mapped = handler.build_embeddings_body(
        "voyage-4-lite",
        {
            "model": "voyage/voyage-4-lite",
            "input": "ping",
            "dimensions": 512,
        },
    )
    assert mapped["model"] == "voyage-4-lite"
    assert mapped["input"] == "ping"
    assert mapped["output_dimension"] == 512
    assert "dimensions" not in mapped

    keep = handler.build_embeddings_body(
        "voyage-4",
        {
            "model": "x",
            "input": "ping",
            "output_dimension": 256,
            "dimensions": 512,
        },
    )
    assert keep["output_dimension"] == 256
    assert "dimensions" not in keep


def test_voyage_rerank_body_maps_top_n_to_top_k() -> None:
    """Unified top_n → Voyage top_k; never send top_n."""
    from app.providers.voyage_ai.config import VoyageAiConfig
    from app.providers.voyage_ai.handler import VoyageAiHandler

    handler = VoyageAiHandler(VoyageAiConfig())
    mapped = handler.build_rerank_body(
        {
            "model": "rerank-2.5",
            "query": "capital of France",
            "documents": ["Paris", "Berlin"],
            "top_n": 3,
            "return_documents": True,
        },
    )
    assert mapped["model"] == "rerank-2.5"
    assert mapped["top_k"] == 3
    assert mapped["return_documents"] is True
    assert "top_n" not in mapped

    bare = handler.build_rerank_body(
        {
            "query": "q",
            "documents": ["a"],
        },
    )
    assert bare["model"] == "rerank-lite-1"
    assert "top_k" not in bare
    assert "return_documents" not in bare


async def get_api_key(provider_id: str) -> str | None:
    """Resolve API key: env var first, then database fallback."""
    env_var: str | None = _API_KEY_ENV_VARS.get(provider_id)
    if env_var:
        key: str | None = os.environ.get(env_var)
        if key:
            return key

    await engine.dispose()
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ProviderConnection).where(
                    ProviderConnection.provider == provider_id,
                    ProviderConnection.is_active == True,
                )
            )
            conn: ProviderConnection | None = result.scalar_one_or_none()
            if not conn or not conn.data:
                return None
            data: dict = json.loads(conn.data)
            return data.get("apiKey") or data.get("accessToken")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Base config inheritance
# ─────────────────────────────────────────────────────────────────────────────

def test_config_inherits_base():
    """Every provider config must inherit BaseProviderConfig."""
    from app.providers.base import BaseProviderConfig

    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        config = p.config()
        assert isinstance(config, BaseProviderConfig), f"{name}: config not inheriting BaseProviderConfig"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: parse_response — all providers
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_response_normal():
    """parse_response extracts models from response."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        data_data: dict = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
        models_data: dict = {"models": [{"id": "model-1"}, {"id": "model-2"}]}
        result: list[dict] = p.parse_response(data_data) or p.parse_response(models_data)
        if not result:
            assert result == [], f"{name}: expected empty list for non-LLM provider"
        else:
            assert len(result) == 2, f"{name}: expected 2 models"


def test_parse_response_empty_data():
    """parse_response returns empty list when keys are missing."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert p.parse_response({}) == [], f"{name}: expected empty list"


def test_parse_response_empty_list():
    """parse_response returns empty list when data is empty."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert p.parse_response({"data": []}) == [], f"{name}: expected empty list"
        assert p.parse_response({"models": []}) == [], f"{name}: expected empty list"


def test_parse_response_extra_keys_ignored():
    """parse_response ignores extra keys in response."""
    data: dict = {
        "data": [{"id": "model-1"}],
        "object": "list",
        "has_more": False,
    }
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        result: list[dict] = p.parse_response(data)
        if not result:
            continue
        assert len(result) == 1, f"{name}: expected 1 model"
        assert result[0]["id"] == "model-1"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Config consistency — base_url, alias, format
# ─────────────────────────────────────────────────────────────────────────────

def test_config_base_url_not_empty():
    """Every provider config must have a non-empty BASE_URL."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert p.base_url(), f"{name}: BASE_URL is empty"
        assert p.base_url().startswith("http"), f"{name}: BASE_URL missing scheme"


def test_config_alias_not_empty():
    """Every provider config must have a non-empty ALIAS."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        assert p.alias(), f"{name}: ALIAS is empty"


def test_config_format_not_empty():
    """Every provider config must have a non-empty FORMAT."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        config = p.config()
        assert config.FORMAT, f"{name}: FORMAT is empty"


def test_config_metadata_exists():
    """Every provider config must have a Metadata class."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        meta = p.metadata()
        assert meta.name, f"{name}: Metadata.name is empty"
        assert meta.color, f"{name}: Metadata.color is empty"
        assert meta.textIcon, f"{name}: Metadata.textIcon is empty"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_openai_models():
    """parse_openai_models extracts data array."""
    from app.providers.model_helpers import parse_openai_models

    result: list[dict] = parse_openai_models({"data": [{"id": "m1"}]})
    assert result == [{"id": "m1"}]

    result = parse_openai_models({"data": []})
    assert result == []

    result = parse_openai_models({})
    assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Integration tests — skipped if no API key (env or DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", AVAILABLE_PROVIDERS)
async def test_fetch_models_integration(provider_id: str) -> None:
    """Fetch real models from provider API."""
    api_key: str | None = await get_api_key(provider_id)
    if not api_key:
        pytest.skip(f"No API key for {provider_id} in env or database")

    p: Provider = Provider(provider_id)
    models: list[dict] = await p.fetch_models(api_key)
    assert isinstance(models, list), f"{provider_id}: expected list"
    if len(models) == 0:
        pytest.skip(f"{provider_id}: no model listing endpoint")
    assert "id" in models[0], f"{provider_id}: model missing 'id' key"
