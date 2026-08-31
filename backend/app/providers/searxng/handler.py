"""SearXNG handler."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result


class SearxngHandler(BaseProviderHandler):
    """Handler for SearXNG search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute SearXNG Search and return normalized results."""
        base_url = self._resolve_base_url(provider_data)
        qp: dict[str, str] = {
            "q": params["query"],
            "format": "json",
            "categories": "general",
        }
        url = f"{base_url}/search?{urlencode(qp)}"
        headers = {"Accept": "application/json"}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("results", [])
        results = [
            make_result("searxng", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("content"),
                "published_at": r.get("publishedDate"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
