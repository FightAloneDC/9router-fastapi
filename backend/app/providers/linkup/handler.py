"""Linkup handler."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class LinkupHandler(BaseProviderHandler):
    """Handler for Linkup search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Linkup Search and return normalized results."""
        from app.services.search_adapters import make_result

        body: dict[str, Any] = {
            "q": params["query"],
            "depth": (params.get("provider_options") or {}).get("depth", "standard"),
            "outputType": "searchResults",
            "maxResults": params.get("max_results", 5),
        }

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}/v1/search"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("results", [])
        results = [
            make_result("linkup", {
                "title": r.get("name"),
                "url": r.get("url"),
                "snippet": r.get("content"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
