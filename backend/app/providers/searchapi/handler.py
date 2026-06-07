"""SearchAPI handler."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.providers.base import BaseProviderHandler


class SearchapiHandler(BaseProviderHandler):
    """Handler for SearchAPI provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute SearchAPI Search and return normalized results."""
        from app.services.search_adapters import make_result

        qp: dict[str, str] = {
            "engine": "google",
            "q": params["query"],
            "api_key": token,
            "num": str(params.get("max_results", 5)),
        }
        if params.get("country"):
            qp["gl"] = params["country"].lower()
        if params.get("language"):
            qp["hl"] = params["language"]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}?{urlencode(qp)}"
        headers = {"Accept": "application/json"}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("organic_results", [])
        results = [
            make_result("searchapi", {
                "title": r.get("title"),
                "url": r.get("link"),
                "snippet": r.get("snippet"),
                "position": r.get("position"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}
