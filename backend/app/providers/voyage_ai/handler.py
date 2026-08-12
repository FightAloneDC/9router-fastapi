"""Voyage AI handler — embedding test call for validation."""

import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class VoyageAiHandler(BaseProviderHandler):
    """Handler for Voyage AI provider."""

    async def validate(self, api_key: str, data: dict | None = None) -> ValidateResult:
        if not api_key:
            return ValidateResult(valid=False, error="API key is required for Voyage AI")

        base_url = self._resolve_base_url(data)
        url = f"{base_url}/embeddings"
        headers = {
            self.config.AUTH_HEADER: f"{self.config.AUTH_PREFIX}{api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.post(url, headers=headers, json={"input": "ping", "model": "voyage-3"})
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(valid=False, error="Invalid API key (unauthorized)", latency_ms=latency)
                if resp.status_code >= 500:
                    return ValidateResult(valid=False, error=f"Voyage returned {resp.status_code}", latency_ms=latency)
                return ValidateResult(valid=True, latency_ms=latency)
            except httpx.ConnectError:
                return ValidateResult(valid=False, error="Cannot connect to Voyage AI API", latency_ms=int((time.monotonic() - start) * 1000))
            except httpx.TimeoutException:
                return ValidateResult(valid=False, error="Connection timed out", latency_ms=int((time.monotonic() - start) * 1000))
            except Exception as e:
                return ValidateResult(valid=False, error=str(e)[:200], latency_ms=int((time.monotonic() - start) * 1000))

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Voyage AI Rerank API: POST /v1/rerank.

        Reference: https://docs.voyageai.com/reference/rerank
        Supports rerank-lite-1, rerank-1, rerank-2 models.
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
            "model": params.get("model", "rerank-lite-1"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }

        url = f"{base_url.rstrip('/')}/rerank"

        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()

        data = resp.json()

        # Normalize response to unified schema
        results = []
        for r in data.get("data", []):
            result_item = {
                "index": r["index"],
                "relevance_score": r["relevance_score"],
            }
            if return_documents and "document" in r:
                result_item["document"] = r["document"]
            results.append(result_item)

        return {
            "results": results,
            "usage": {"queries_used": 1, "total_tokens": data.get("usage", {}).get("total_tokens", 0)},
            "metrics": {"response_time_ms": data.get("duration", 0)},
            "errors": [],
        }
