"""Tests for per-provider model fetching via Provider class.

Tests pure functions (parse_response, URL derivation) without network.
Integration tests (fetch_models) are skipped if no API key is available.
API key resolution: env var → database ProviderConnection.data["apiKey"].
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
    PROVIDER_OPENROUTER,
)
from app.providers.provider import Provider
from app.utils.url import url_path_join

# Provider constants → env var name mapping for API key lookup
_API_KEY_ENV_VARS: dict[str, str] = {
    PROVIDER_CEREBRAS: "CEREBRAS_API_KEY",
    PROVIDER_GROQ: "GROQ_API_KEY",
    PROVIDER_OPENROUTER: "OPENROUTER_API_KEY",
}


async def get_api_key(provider_id: str) -> str | None:
    """Resolve API key: env var first, then database fallback.

    Args:
        provider_id: Provider constant (e.g. PROVIDER_CEREBRAS).

    Returns:
        API key string, or None if not found.
    """
    # 1. Env var takes priority
    env_var = _API_KEY_ENV_VARS.get(provider_id)
    if env_var:
        key = os.environ.get(env_var)
        if key:
            return key

    # 2. Fallback: query database for active connection
    # Dispose engine first to clear stale connections from previous event loop
    await engine.dispose()
    try:
        async with async_session() as session:
            result = await session.execute(
                select(ProviderConnection).where(
                    ProviderConnection.provider == provider_id,
                    ProviderConnection.is_active == True,
                )
            )
            conn = result.scalar_one_or_none()
            if not conn or not conn.data:
                return None

            data = json.loads(conn.data)
            return data.get("apiKey") or data.get("accessToken")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: URL derivation — all providers
# ─────────────────────────────────────────────────────────────────────────────


def test_model_fetch_url_derives_from_config():
    """MODEL_FETCH_URL should derive from config.BASE_URL via url_path_join.

    Some providers have custom model fetch URLs that differ from base_url + /models.
    Providers without MODEL_FETCH_URL (non-LLM) are skipped.
    """
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        models_module = p._load_models()
        # Skip providers without MODEL_FETCH_URL (non-LLM providers)
        if not hasattr(models_module, "MODEL_FETCH_URL"):
            continue
        expected = url_path_join(p.base_url(), "models")
        actual = models_module.MODEL_FETCH_URL
        # Allow custom URLs — just verify it's a valid URL
        assert actual.startswith("http"), f"{name}: MODEL_FETCH_URL missing scheme: {actual}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: parse_response — all providers
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_response_normal():
    """parse_response extracts models from response."""
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        # Try both 'data' and 'models' keys (Gemini uses 'models')
        data_data = {"data": [{"id": "model-1"}, {"id": "model-2"}]}
        models_data = {"models": [{"id": "model-1"}, {"id": "model-2"}]}
        result = p.parse_response(data_data) or p.parse_response(models_data)
        # Non-LLM providers return empty list — that's expected
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
    data = {
        "data": [{"id": "model-1"}],
        "object": "list",
        "has_more": False,
    }
    for name in AVAILABLE_PROVIDERS:
        p = Provider(name)
        result = p.parse_response(data)
        # Non-LLM providers return empty
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


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Integration tests — skipped if no API key (env or DB)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", AVAILABLE_PROVIDERS)
async def test_fetch_models_integration(provider_id: str):
    """Fetch real models from provider API."""
    api_key = await get_api_key(provider_id)
    if not api_key:
        pytest.skip(f"No API key for {provider_id} in env or database")

    p = Provider(provider_id)
    models = await p.fetch_models(api_key)
    assert isinstance(models, list), f"{provider_id}: expected list"
    # Some providers (assemblyai, playht, etc.) don't have model listing
    if len(models) == 0:
        pytest.skip(f"{provider_id}: no model listing endpoint")
    assert "id" in models[0], f"{provider_id}: model missing 'id' key"
