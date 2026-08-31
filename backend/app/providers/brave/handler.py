"""Brave Search handler."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result


class BraveHandler(BaseProviderHandler):
    """Handler for Brave Search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Brave Search and return normalized results."""
        endpoint = "/news/search" if params.get("search_type") == "news" else "/web/search"
        qp: dict[str, str] = {"q": params["query"], "count": str(params.get("max_results", 5))}
        if params.get("country"):
            qp["country"] = params["country"]
        if params.get("language"):
            qp["search_lang"] = params["language"]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}{endpoint}?{urlencode(qp)}"
        headers = {"Accept": "application/json", "X-Subscription-Token": token}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        container = data.get("news" if params.get("search_type") == "news" else "web", data)
        items = container.get("results", [])
        results = [
            make_result("brave-search", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("description"),
                "published_at": r.get("page_age") or r.get("age"),
                "favicon_url": (r.get("meta_url") or {}).get("favicon"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": container.get("totalCount")}
