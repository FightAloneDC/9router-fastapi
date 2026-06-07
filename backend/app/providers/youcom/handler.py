"""You.com handler."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.providers.base import BaseProviderHandler


class YoucomHandler(BaseProviderHandler):
    """Handler for You.com search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute You.com Search and return normalized results."""
        from app.services.search_adapters import make_result

        qp: dict[str, str] = {"query": params["query"], "count": str(params.get("max_results", 5))}
        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}/search?{urlencode(qp)}"
        headers = {"Accept": "application/json", "X-API-Key": token}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        hits = data.get("results", data.get("hits", {}))
        items = hits.get("web", hits) if isinstance(hits, dict) else hits
        if not isinstance(items, list):
            items = []
        results = [
            make_result("youcom", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": (r.get("snippets") or [None])[0] if r.get("snippets") else None,
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
