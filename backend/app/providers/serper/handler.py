"""Serper handler."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result


class SerperHandler(BaseProviderHandler):
    """Handler for Serper search provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Serper Search and return normalized results."""
        endpoint = "/news" if params.get("search_type") == "news" else "/search"
        body: dict[str, Any] = {"q": params["query"], "num": params.get("max_results", 5)}
        if params.get("country"):
            body["gl"] = params["country"].lower()
        if params.get("language"):
            body["hl"] = params["language"]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}{endpoint}"
        headers = {"Content-Type": "application/json", "X-API-Key": token}

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("organic", data.get("results", []))
        results = [
            make_result("serper", {
                "title": r.get("title"),
                "url": r.get("link") or r.get("url"),
                "snippet": r.get("snippet"),
                "position": r.get("position"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
