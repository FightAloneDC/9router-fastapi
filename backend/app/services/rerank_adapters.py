"""Rerank adapters for /v1/rerank endpoint.

Provider-specific rerank logic lives in ``backend/app/providers/<provider>/handler.py``
via ``execute_rerank()`` method (PS pattern).

This file provides:
- ``execute_rerank()`` orchestrator that dispatches to provider handlers
"""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.provider import Provider


async def execute_rerank(
    client: httpx.AsyncClient,
    provider_id: str,
    params: dict,
    token: str,
    provider_data: dict | None = None,
) -> dict:
    """Execute a rerank request and return normalized results.

    Dispatches to provider handler's ``execute_rerank()`` method (PS pattern).

    Args:
        client: httpx async client
        provider_id: rerank provider ID
        params: normalized rerank params (query, documents, top_n, etc.)
        token: API key/token
        provider_data: connection-specific data (baseUrl, workspaceId, etc.)

    Returns:
        Unified rerank response dict.

    Raises:
        ValueError: if provider doesn't support rerank
    """
    if provider_data is None:
        provider_data = {}

    try:
        p = Provider(provider_id)
        handler = p.handler()
    except (ValueError, ModuleNotFoundError):
        raise ValueError(f"Unsupported rerank provider: {provider_id}")

    if not hasattr(handler, "execute_rerank"):
        raise ValueError(f"Provider '{provider_id}' does not support rerank")

    normalized = await handler.execute_rerank(
        client,
        params=params,
        token=token,
        provider_data=provider_data,
    )

    return {
        "provider": provider_id,
        "query": params["query"],
        "results": normalized["results"],
        "usage": normalized.get("usage", {"queries_used": 1}),
        "metrics": normalized.get("metrics", {}),
        "errors": normalized.get("errors", []),
    }
