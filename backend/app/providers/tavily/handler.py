"""Tavily provider handler."""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import BaseProviderHandler


class TavilyHandler(BaseProviderHandler):
    """Handler for Tavily provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Tavily Search and return normalized results."""
        from app.services.search_adapters import make_result, parse_domain_filter

        body: dict[str, Any] = {
            "query": params["query"],
            "max_results": params.get("max_results", 5),
            "topic": "news" if params.get("search_type") == "news" else "general",
        }
        includes, excludes = parse_domain_filter(params.get("domain_filter"))
        if includes:
            body["include_domains"] = includes
        if excludes:
            body["exclude_domains"] = excludes
        if params.get("country"):
            body["country"] = params["country"]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}/search"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("results", [])
        results = [
            make_result("tavily", {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("content", ""),
                "score": r.get("score"),
                "published_at": r.get("published_date"),
                "full_text": r.get("raw_content"),
                "text_format": "text",
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": len(results)}

    def build_webfetch_request(
        self, url: str, fmt: str, api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """Build web fetch request for Tavily."""
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        fetch_url = f"{self.config.BASE_URL}/extract"
        body = {"urls": [url], "format": fmt}
        return "POST", headers, fetch_url, body
