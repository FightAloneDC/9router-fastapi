"""Cohere provider — rerank endpoint implementation."""

from __future__ import annotations

import httpx

from app.providers.base import BaseProviderHandler


class CohereHandler(BaseProviderHandler):
    """Handler for Cohere provider."""

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Cohere Rerank API: POST /rerank.

        Reference: https://docs.cohere.com/reference/rerank-1
        """
        query = params["query"]
        documents = params["documents"]
        top_n = params.get("top_n", 10)
        return_documents = params.get("return_documents", False)

        # Use native Cohere API base (not compatibility mode)
        base_url = "https://api.cohere.com/v1/rerank"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Client-Name": "9router-v1.0",
        }

        body = {
            "model": params.get("model", "rerank-english-v2.0"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        resp = await client.post(base_url, json=body, headers=headers)
        resp.raise_for_status()

        data = resp.json()

        # Normalize response to unified schema
        results = []
        for r in data.get("results", []):
            result_item = {
                "index": r["index"],
                "relevance_score": r["relevance_score"],
            }
            if return_documents and "document" in r:
                result_item["document"] = r["document"]
            results.append(result_item)

        return {
            "results": results,
            "usage": {"queries_used": 1},
            "metrics": {"response_tokens": data.get("meta", {}).get("tokens", {})},
            "errors": [],
        }
