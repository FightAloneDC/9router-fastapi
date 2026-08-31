"""Exa provider handler."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result, parse_domain_filter


class ExaHandler(BaseProviderHandler):
    """Handler for Exa provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Exa Search and return normalized results."""
        includes, excludes = parse_domain_filter(params.get("domain_filter"))
        body: dict[str, Any] = {
            "query": params["query"],
            "numResults": params.get("max_results", 5),
            "type": "auto",
            "text": True,
            "highlights": True,
        }
        if includes:
            body["includeDomains"] = includes
        if excludes:
            body["excludeDomains"] = excludes
        if params.get("search_type") == "news":
            body["category"] = "news"

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}/search"
        headers = {"Content-Type": "application/json", "x-api-key": token}

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("results", [])
        results = [
            make_result("exa", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": (r.get("highlights") or [None])[0] if r.get("highlights") else None,
                "score": r.get("score"),
                "published_at": r.get("publishedDate"),
                "full_text": r.get("text"),
                "text_format": "text",
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Exa."""
        headers: dict[str, str] = {}
        if api_key:
            headers["x-api-key"] = api_key
        fetch_url = f"{self.config.BASE_URL}/contents"
        body = {"urls": [url], "text": True}
        return "POST", headers, fetch_url, body
