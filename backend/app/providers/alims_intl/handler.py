"""Alibaba Studio request compatibility handler.

Supports rerank endpoints for qwen3-rerank and other DashScope models.
Reference: https://www.alibabacloud.com/help/en/model-studio/text-rerank-api
"""

from __future__ import annotations

import httpx

from app.providers.alims_intl.config import AlimsIntlConfig
from app.providers.base import BaseProviderHandler

_CONFIG = AlimsIntlConfig()


def rerank_url(base_url: str) -> str:
    """Build the DashScope rerank endpoint for a chat-compatible base.

    Public DashScope hosts use ``/compatible-api/v1/reranks``.
    Workspace MAAS hosts keep ``/compatible-mode/v1/reranks``.
    """
    mode = _CONFIG.RERANK_COMPAT_MODE_SUFFIX
    api = _CONFIG.RERANK_COMPAT_API_SUFFIX
    root = (base_url or "").rstrip("/")
    for suffix in (mode, api):
        if root.endswith(suffix):
            root = root[: -len(suffix)]
            break
    public = {
        h.rstrip("/") for h in _CONFIG.RERANK_PUBLIC_HOSTS
    }
    if root in public:
        return f"{root}{api}/reranks"
    return f"{root}{mode}/reranks"


class AlimsIntlHandler(BaseProviderHandler):
    """Adapt OpenAI developer messages for Alibaba Studio."""

    async def fetch_models(
        self,
        api_key: str,
        data: dict | None = None,
    ) -> list[dict]:
        """Live /models plus docs-only rerank rows."""
        from app.providers.alims_intl.models import (
            fetch_models as load_catalog,
        )

        models = await load_catalog(api_key, data)
        normalized = [
            self._normalize_model(item) for item in models
        ]
        return [item for item in normalized if item.get("id")]

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        """Map the unsupported developer role to system."""
        messages = body.get("messages")
        if not isinstance(messages, list):
            return headers, body

        normalized_messages = [
            {
                **message,
                "role": "system"
                if isinstance(message, dict)
                and message.get("role") == "developer"
                else message.get("role"),
            }
            if isinstance(message, dict)
            else message
            for message in messages
        ]

        cleaned = {**body, "messages": normalized_messages}
        cleaned.pop("think", None)
        cleaned.pop("thinking", None)
        effort = cleaned.get("reasoning_effort")
        if effort not in ("low", "medium", "high", "xhigh", "max"):
            cleaned.pop("reasoning_effort", None)
            cleaned.pop("reasoning", None)
        return {**headers}, cleaned

    async def execute_rerank(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        params: dict,
        provider_data: dict | None = None,
    ) -> dict:
        """DashScope Text Rerank (OpenAI-compatible flat body).

        Public intl host: POST …/compatible-api/v1/reranks.
        Workspace MAAS: POST …/compatible-mode/v1/reranks.
        """
        query = params["query"]
        documents = params["documents"]
        top_n = params.get("top_n", 10)
        return_documents = params.get("return_documents", False)
        instruct = params.get("instruct")

        base_url = self._resolve_base_url(provider_data or {})

        body: dict = {
            "model": params.get("model", "qwen3-rerank"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        if instruct:
            body["instruct"] = instruct

        url = rerank_url(base_url)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resp = await client.post(url, json=body, headers=headers)
        resp.raise_for_status()

        data = resp.json()

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
            "usage": {
                "total_tokens": data.get("usage", {}).get(
                    "total_tokens", 0,
                ),
            },
            "metrics": {
                "response_time_ms": data.get("duration", 0),
                "request_id": data.get(
                    "id", data.get("request_id"),
                ),
            },
            "errors": [],
        }
