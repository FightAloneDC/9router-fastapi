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

    async def fetch_models(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> list[dict]:
        """Return the documented catalog. Voyage has no list-models API."""
        from app.providers.voyage_ai.models import fetch_models as load_catalog

        models = await load_catalog(api_key, data)
        normalized = [self._normalize_model(item) for item in models]
        return [item for item in normalized if item.get("id")]

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Voyage AI Rerank API: POST /v1/rerank.

        Reference: https://docs.voyageai.com/reference/reranker-api
        Unified ``top_n`` maps to Voyage ``top_k``.
        """
        return_documents = bool(params.get("return_documents", False))
        base_url = self._resolve_base_url(provider_data or {})
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = self.build_rerank_body(params)
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
            "usage": {
                "queries_used": 1,
                "total_tokens": data.get("usage", {}).get(
                    "total_tokens", 0
                ),
            },
            "metrics": {"response_time_ms": data.get("duration", 0)},
            "errors": [],
        }

    def build_rerank_body(self, params: dict) -> dict:
        """Map unified /v1/rerank params to Voyage API body.

        Official docs (retrieved 2026-08-25):
        https://docs.voyageai.com/reference/reranker-api

        Voyage accepts ``top_k`` (and rejects Cohere-style
        ``top_n``). ``return_documents`` is optional.
        """
        body: dict = {
            "model": params.get("model", "rerank-lite-1"),
            "query": params["query"],
            "documents": params["documents"],
        }
        top_n = params.get("top_n")
        if top_n is not None:
            body["top_k"] = top_n
        if params.get("return_documents"):
            body["return_documents"] = True
        return body

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Map OpenAI-compat embeddings body to Voyage API.

        Official docs (retrieved 2026-08-25):
        https://docs.voyageai.com/reference/embeddings-api.md

        Voyage accepts ``output_dimension`` (and rejects OpenAI's
        ``dimensions``). Keep other OpenAI-compat keys that Voyage
        also documents (``input_type``, ``truncation``,
        ``output_dtype``, ``encoding_format``).
        """
        out: dict = {**body, "model": model}
        dims = out.pop("dimensions", None)
        if (
            dims is not None
            and out.get("output_dimension") is None
        ):
            out["output_dimension"] = dims
        return out
