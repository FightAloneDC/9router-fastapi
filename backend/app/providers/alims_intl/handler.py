"""Alibaba Studio request compatibility handler.

Supports rerank endpoints for qwen3-rerank and other DashScope models.
Reference: https://www.alibabacloud.com/help/en/model-studio/text-rerank-api
"""

from __future__ import annotations

import httpx

from app.providers.base import BaseProviderHandler

_COMPAT_SUFFIX = "/compatible-mode/v1"


def rerank_url(base_url: str) -> str:
    """Compatible-mode rerank endpoint for any base URL shape."""
    root = (base_url or "").rstrip("/")
    if root.endswith(_COMPAT_SUFFIX):
        root = root[: -len(_COMPAT_SUFFIX)]
    return f"{root}{_COMPAT_SUFFIX}/reranks"


class AlimsIntlHandler(BaseProviderHandler):
    """Adapt OpenAI developer messages for Alibaba Studio."""

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        """Map the unsupported developer role to the supported system role."""
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
        """DashScope Rerank API via MAAS (Model-as-a-Service).

        Supports qwen3-rerank and gte-rerank-v2 models.
        Reference: https://www.alibabacloud.com/help/en/model-studio/text-rerank-api

        Regional endpoints differ by workspace ID:
          - China (Beijing): https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1
          - Singapore: https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
          - EU Frankfurt: https://{WorkspaceId}.eu-central-1.maas.aliyuncs.com/compatible-mode/v1

        For qwen3-rerank without workspace routing, use compatible-mode endpoints:
          - Beijing: POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-api/v1/reranks
          - Singapore: POST https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/reranks
        """
        query = params["query"]
        documents = params["documents"]
        top_n = params.get("top_n", 10)
        return_documents = params.get("return_documents", False)
        instruct = params.get("instruct")

        base_url = self._resolve_base_url(provider_data or {})

        # Build request body for qwen3-rerank format (flat structure)
        body: dict = {
            "model": params.get("model", "qwen3-rerank"),
            "query": query,
            "documents": documents,
            "top_n": top_n,
        }
        if instruct:
            body["instruct"] = instruct

        # Use compatible-mode endpoint for qwen3-rerank
        url = rerank_url(base_url)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

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
            "usage": {"total_tokens": data.get("usage", {}).get("total_tokens", 0)},
            "metrics": {
                "response_time_ms": data.get("duration", 0),
                "request_id": data.get("id", data.get("request_id")),
            },
            "errors": [],
        }
