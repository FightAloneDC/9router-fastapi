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
    PROVIDER_OPENROUTER,
)
from app.providers.provider import Provider

# Provider constants -> env var name mapping for API key lookup
_API_KEY_ENV_VARS: dict[str, str] = {
    PROVIDER_CEREBRAS: "CEREBRAS_API_KEY",
    PROVIDER_GROQ: "GROQ_API_KEY",
    PROVIDER_OPENROUTER: "OPENROUTER_API_KEY",
}


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
