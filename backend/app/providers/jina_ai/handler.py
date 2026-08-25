"""Jina AI handler — embeddings, rerank, search, reader."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult
from app.services.outbound_proxy import create_upstream_client


class JinaAiHandler(BaseProviderHandler):
    """Handler for Jina AI (api / s / r hosts, one key)."""

    def _search_base(self) -> str:
        """Search host from config.SEARCH_BASE_URL (not BASE_URL)."""
        return str(self.config.SEARCH_BASE_URL).rstrip("/")

    def _reader_base(self) -> str:
        """Reader host from config.READER_BASE_URL (not BASE_URL)."""
        return str(self.config.READER_BASE_URL).rstrip("/")

    def _json_headers(self, api_key: str) -> dict[str, str]:
        headers: dict[str, str] = {
            self.config.AUTH_HEADER: (
                f"{self.config.AUTH_PREFIX}{api_key}"
            ),
            "Content-Type": "application/json",
        }
        if self.config.EXTRA_HEADERS:
            headers.update(self.config.EXTRA_HEADERS)
        return headers

    async def validate(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> ValidateResult:
        if not api_key:
            return ValidateResult(
                valid=False,
                error="API key is required for Jina AI",
            )

        base_url = self._resolve_base_url(data)
        url = f"{base_url.rstrip('/')}/embeddings"
        headers = self._json_headers(api_key)

        start = time.monotonic()
        async with create_upstream_client(timeout=15.0) as client:
            try:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": self.config.DEFAULT_EMBEDDING_MODEL,
                        "input": ["ping"],
                    },
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code in (401, 403):
                    return ValidateResult(
                        valid=False,
                        error="Invalid API key (unauthorized)",
                        latency_ms=latency,
                    )
                if resp.status_code >= 500:
                    return ValidateResult(
                        valid=False,
                        error=f"Jina returned {resp.status_code}",
                        latency_ms=latency,
                    )
                return ValidateResult(
                    valid=True,
                    latency_ms=latency,
                )
            except httpx.ConnectError:
                return ValidateResult(
                    valid=False,
                    error="Cannot connect to Jina AI API",
                    latency_ms=int(
                        (time.monotonic() - start) * 1000
                    ),
                )
            except httpx.TimeoutException:
                return ValidateResult(
                    valid=False,
                    error="Connection timed out",
                    latency_ms=int(
                        (time.monotonic() - start) * 1000
                    ),
                )
            except Exception as e:
                return ValidateResult(
                    valid=False,
                    error=str(e)[:200],
                    latency_ms=int(
                        (time.monotonic() - start) * 1000
                    ),
                )

    async def fetch_models(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> list[dict]:
        """Live /models plus synthetic search/reader rows."""
        from app.providers.jina_ai.models import (
            fetch_models as load_catalog,
        )

        models = await load_catalog(api_key, data)
        normalized = [
            self._normalize_model(item) for item in models
        ]
        return [item for item in normalized if item.get("id")]

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """Jina AI Rerank API: POST /v1/rerank."""
        return_documents = bool(
            params.get("return_documents", False)
        )
        base_url = self._resolve_base_url(provider_data or {})
        headers = self._json_headers(token)
        body = self.build_rerank_body(params)
        url = f"{base_url.rstrip('/')}/rerank"

        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for r in data.get("results", []):
            item = {
                "index": r["index"],
                "relevance_score": r["relevance_score"],
            }
            if return_documents and "document" in r:
                item["document"] = r["document"]
            results.append(item)

        usage = data.get("usage") or {}
        total_tokens = int(
            usage.get("total_tokens")
            or usage.get("prompt_tokens")
            or 0
        )
        return {
            "results": results,
            "usage": {
                "queries_used": 1,
                "total_tokens": total_tokens,
                "prompt_tokens": int(
                    usage.get("prompt_tokens") or total_tokens
                ),
            },
            "metrics": {
                "response_time_ms": data.get("duration", 0),
            },
            "errors": [],
        }

    def build_rerank_body(self, params: dict) -> dict:
        """Map unified /v1/rerank params to Jina body."""
        body: dict = {
            "model": params.get(
                "model",
                self.config.DEFAULT_RERANK_MODEL,
            ),
            "query": params["query"],
            "documents": params["documents"],
        }
        top_n = params.get("top_n")
        if top_n is not None:
            body["top_n"] = top_n
        if "return_documents" in params:
            body["return_documents"] = bool(
                params.get("return_documents")
            )
        return body

    def build_embeddings_body(self, model: str, body: dict) -> dict:
        """Map OpenAI-compat embeddings body to Jina API."""
        out: dict = {**body, "model": model}
        raw_input = out.get("input")
        if isinstance(raw_input, str):
            out["input"] = [raw_input]
        enc = out.pop("encoding_format", None)
        if (
            enc is not None
            and out.get("embedding_type") is None
        ):
            out["embedding_type"] = enc
        return out

    def build_search_body(self, params: dict[str, Any]) -> dict:
        """Map unified /v1/search params to SEARCH_BASE_URL body.

        Official docs (retrieved 2026-08-25): docs.jina.ai —
        ``q`` required; optional ``gl``, ``hl``, ``num``, ``page``,
        ``location``.
        """
        body: dict[str, Any] = {"q": params["query"]}
        country = params.get("country")
        if country:
            body["gl"] = str(country)
        language = params.get("language")
        if language:
            body["hl"] = str(language)
        max_results = params.get("max_results")
        if max_results is not None:
            body["num"] = int(max_results)
        page = params.get("page")
        if page is not None:
            body["page"] = int(page)
        location = params.get("location")
        if location:
            body["location"] = str(location)
        return body

    async def execute_search(
        self,
        client: httpx.AsyncClient,
        *,
        params: dict[str, Any],
        token: str,
        provider_data: dict | None = None,
    ) -> dict[str, Any]:
        """POST SEARCH_BASE_URL — ignore connection baseUrl (api)."""
        del provider_data
        from app.services.search_adapters import make_result

        url = self._search_base() + "/"
        headers = self._json_headers(token)
        body = self.build_search_body(params)
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("data")
        if not isinstance(raw_items, list):
            raw_items = data.get("results") or []
        if not isinstance(raw_items, list):
            raw_items = []

        provider_id = self.config.PROVIDER_ID
        results = []
        for i, row in enumerate(raw_items):
            if not isinstance(row, dict):
                continue
            snippet = (
                row.get("description")
                or row.get("snippet")
                or row.get("content")
                or ""
            )
            results.append(
                make_result(
                    provider_id,
                    {
                        "title": row.get("title") or "",
                        "url": row.get("url") or "",
                        "snippet": snippet,
                        "full_text": row.get("content"),
                        "text_format": "text",
                        "favicon_url": row.get("favicon"),
                    },
                    i,
                )
            )

        meta = data.get("meta") if isinstance(data, dict) else None
        tokens = 0
        if isinstance(meta, dict):
            usage_meta = meta.get("usage")
            if isinstance(usage_meta, dict):
                tokens = int(usage_meta.get("tokens") or 0)
        if not tokens:
            try:
                tokens = int(resp.headers.get("x-usage-tokens") or 0)
            except (TypeError, ValueError):
                tokens = 0

        out: dict[str, Any] = {
            "results": results,
            "totalResults": len(results),
        }
        if tokens:
            out["usage"] = {
                "total_tokens": tokens,
                "prompt_tokens": tokens,
            }
        return out

    def build_webfetch_request(
        self,
        url: str,
        fmt: str,
        api_key: str,
    ) -> tuple[str, dict[str, str], str, dict | None]:
        """GET READER_BASE_URL/{url} with X-Return-Format."""
        headers: dict[str, str] = {}
        if api_key:
            headers[self.config.AUTH_HEADER] = (
                f"{self.config.AUTH_PREFIX}{api_key}"
            )
        fmt_map = self.config.RETURN_FORMAT_MAP
        return_fmt = fmt_map.get(
            (fmt or "markdown").strip().lower(),
            "markdown",
        )
        headers["X-Return-Format"] = return_fmt
        fetch_url = f"{self._reader_base()}/{url}"
        return "GET", headers, fetch_url, None
