"""Jina AI provider — rerank endpoint implementation."""

from __future__ import annotations

import httpx

from app.providers.base import BaseProviderHandler


class JinaAiHandler(BaseProviderHandler):
    """Handler for Jina AI provider."""

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Jina AI Rerank API: POST /v1/rerank.

        Reference: https://jina.ai/api-dashboard/reranker
        """
        query = params["query"]
        documents = params["documents"]
        top_n = params.get("top_n", 10)
        return_documents = params.get("return_documents", False)

        base_url = self._resolve_base_url(provider_data or {})

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        body = {
            "model": params.get("model", "jina-reranker-v1"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": return_documents,
        }

        url = f"{base_url.rstrip('/')}/rerank"

        resp = await client.post(url, json=body, headers=headers)
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
            "metrics": {"response_time_ms": data.get("duration", 0)},
            "errors": [],
        }
