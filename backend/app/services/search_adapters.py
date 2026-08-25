"""Search adapters for /v1/search endpoint.

Provider-specific search logic lives in ``backend/app/providers/<provider>/handler.py``
via ``execute_search()`` method (PS pattern).

This file provides:
- Shared utilities (``parse_domain_filter``, ``make_result``)
- ``execute_search()`` orchestrator that dispatches to provider handlers
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Shared utilities
# ─────────────────────────────────────────────────────────────────────────────


def parse_domain_filter(domain_filter: list[str] | None) -> tuple[list[str], list[str]]:
    """Split domain filter into includes/excludes (excludes prefixed with '-')."""
    if not domain_filter:
        return [], []
    includes = [d for d in domain_filter if not d.startswith("-")]
    excludes = [d[1:] for d in domain_filter if d.startswith("-")]
    return includes, excludes


def make_result(provider_id: str, item: dict, idx: int) -> dict:
    """Build a unified SearchResult object."""
    url = item.get("url", "")
    full_text = item.get("full_text")
    content_block = None
    if full_text:
        content_block = {
            "format": item.get("text_format", "text"),
            "text": full_text,
            "length": len(full_text),
        }

    return {
        "title": item.get("title", ""),
        "url": url,
        "display_url": url.replace("https://", "").replace("http://", "").split("?")[0] if url else None,
        "snippet": item.get("snippet", ""),
        "position": idx + 1,
        "score": min(1.0, max(0.0, item["score"])) if isinstance(item.get("score"), (int, float)) else None,
        "published_at": item.get("published_at"),
        "favicon_url": item.get("favicon_url"),
        "content": content_block,
        "metadata": {
            "author": item.get("author"),
            "language": None,
            "source_type": item.get("source_type"),
            "image_url": item.get("image_url"),
        },
        "citation": {
            "provider": provider_id,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "rank": idx + 1,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch
# ─────────────────────────────────────────────────────────────────────────────


async def execute_search(
    client: httpx.AsyncClient,
    provider_id: str,
    params: dict,
    token: str,
    provider_data: dict | None = None,
) -> dict:
    """Execute a search request and return normalized results.

    Dispatches to provider handler's ``execute_search()`` method (PS pattern).

    Args:
        client: httpx async client
        provider_id: search provider ID
        params: normalized search params (query, max_results, etc.)
        token: API key/token
        provider_data: connection-specific data (baseUrl, cx, etc.)

    Returns:
        Unified search response dict.
    """
    if provider_data is None:
        provider_data = {}

    from app.providers.provider import Provider

    try:
        p = Provider(provider_id)
        handler = p.handler()
    except (ValueError, ModuleNotFoundError):
        raise ValueError(f"Unsupported search provider: {provider_id}")

    if not hasattr(handler, "execute_search"):
        raise ValueError(f"Provider '{provider_id}' does not support search")

    normalized = await handler.execute_search(
        client,
        params=params,
        token=token,
        provider_data=provider_data,
    )

    usage: dict[str, Any] = {"queries_used": 1}
    raw_usage = normalized.get("usage")
    if isinstance(raw_usage, dict):
        for key in ("total_tokens", "prompt_tokens", "completion_tokens"):
            if key in raw_usage and raw_usage[key] is not None:
                usage[key] = int(raw_usage[key])

    return {
        "provider": provider_id,
        "query": params["query"],
        "results": normalized["results"],
        "answer": None,
        "usage": usage,
        "metrics": {
            "total_results_available": normalized.get("totalResults"),
        },
        "errors": [],
    }
