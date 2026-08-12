"""Shared model fetching helpers.

Most providers follow the same pattern:
  GET {BASE_URL}/models → {data: [...]}
  Auth via header (Authorization: Bearer ...) or query param (?key=...).

This module provides reusable functions so per-provider models.py
can be reduced to ~8 lines for standard providers.
"""

from typing import Callable

from app.providers.base import BaseProviderConfig
from app.services.outbound_proxy import create_upstream_client
from app.utils.url import url_path_join

TIMEOUT: float = 15.0


def parse_openai_models(data: dict) -> list[dict]:
    """Standard OpenAI-compatible response: {data: [...]}"""
    return data.get("data", [])


async def fetch_models_header_auth(
    config: BaseProviderConfig,
    api_key: str,
    parse_fn: Callable[[dict], list[dict]] = parse_openai_models,
) -> list[dict]:
    """Shared fetch_models for providers using header-based auth.

    Covers ~55+ providers (OpenAI, Anthropic, DeepSeek, Groq, etc.).
    Only BASE_URL, AUTH_HEADER, AUTH_PREFIX differ — all from config.
    """
    url: str = url_path_join(config.BASE_URL, "models")
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if config.AUTH_HEADER:
        headers[config.AUTH_HEADER] = f"{config.AUTH_PREFIX}{api_key}"

    if config.EXTRA_HEADERS:
        headers.update(config.EXTRA_HEADERS)

    async with create_upstream_client(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return parse_fn(resp.json())


async def fetch_models_query_auth(
    config: BaseProviderConfig,
    api_key: str,
    parse_fn: Callable[[dict], list[dict]] = parse_openai_models,
) -> list[dict]:
    """Shared fetch_models for providers using query-param auth (Gemini, etc.)."""
    url: str = url_path_join(config.BASE_URL, "models")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    params: dict[str, str] = {config.AUTH_QUERY_PARAM: api_key}

    async with create_upstream_client(timeout=TIMEOUT) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return parse_fn(resp.json())
