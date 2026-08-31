"""Google PSE handler."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.providers.base import BaseProviderHandler
from app.services.search_adapters import make_result


class GooglePseHandler(BaseProviderHandler):
    """Handler for Google Programmable Search Engine provider."""

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """Execute Google PSE Search and return normalized results."""
        pd = provider_data or {}
        cx = pd.get("cx") or (params.get("provider_options") or {}).get("cx")
        if not cx:
            raise ValueError("Google PSE requires 'cx' (search engine ID) in providerSpecificData")

        qp: dict[str, str] = {
            "key": token, "cx": cx, "q": params["query"],
            "num": str(min(params.get("max_results", 5), 10)),
        }
        if params.get("country"):
            qp["gl"] = params["country"].lower()
        if params.get("language"):
            qp["hl"] = params["language"]

        time_range = params.get("time_range")
        if time_range and time_range != "any":
            date_map = {"day": "d1", "week": "w1", "month": "m1", "year": "y1"}
            if time_range in date_map:
                qp["dateRestrict"] = date_map[time_range]

        base_url = self._resolve_base_url(provider_data)
        url = f"{base_url}?{urlencode(qp)}"
        headers = {"Accept": "application/json"}

        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        results = [
            make_result("google-pse", {
                "title": r.get("title"),
                "url": r.get("link"),
                "snippet": r.get("snippet"),
                "image_url": (r.get("pagemap") or {}).get("cse_image", [{}])[0].get("src"),
            }, i) for i, r in enumerate(items)
        ]
        return {"results": results, "totalResults": data.get("searchInformation", {}).get("totalResults")}
