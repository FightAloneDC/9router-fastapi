"""Perplexity handler."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result


class PerplexityHandler(BaseProviderHandler):
    """Handler for Perplexity search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Perplexity Search and return normalized results."""
        body: dict[str, Any] = {"query": params["query"], "max_results": params.get("max_results", 5)}
        if params.get("country"):
            body["country"] = params["country"]
        if params.get("language"):
            body["search_language_filter"] = [params["language"]]
        if params.get("domain_filter"):
            body["search_domain_filter"] = params["domain_filter"]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}/search"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("results", [])
        results = [
            make_result("perplexity", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("snippet"),
                "published_at": r.get("published_date"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
