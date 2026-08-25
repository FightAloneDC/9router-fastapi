"""POST /v1/rerank — Unified rerank proxy endpoint."""

import json
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.api_key_auth import validate_api_key
from app.services.proxy import _resolve_provider_alias
from app.services.rerank_adapters import execute_rerank
from app.providers.provider import Provider
from app.services.usage_tracking import save_request_tracking
from app.models.provider import ProviderConnection
from app.services.outbound_proxy import (
    ProxyRequiredError,
    create_upstream_client,
    proxy_for_connection,
)

router = APIRouter()


@router.post("/rerank")
async def rerank_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """Unified rerank proxy endpoint.

    Routes rerank queries to dedicated rerank APIs (cohere, jina_ai, voyage_ai,
    alims-intl, etc.) and returns normalized results.

    Body:
      - model or provider (required): rerank provider ID
      - query (required): search query string
      - documents (required): array of document strings or objects
      - top_n: max results (default 10, max 100)
      - return_documents: boolean (include doc text in response)
      - language: optional language code
      - provider_options: provider-specific options

    Response: unified rerank results format.
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    provider_raw: str | None = body.get("model") or body.get("provider")
    query: str | None = body.get("query")
    documents: list | None = body.get("documents")

    if not provider_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model or provider",
        )
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: query",
        )
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: documents",
        )

    # OpenAI-style "alias/model-id" → provider + upstream model.
    upstream_model: str | None = None
    if "/" in provider_raw:
        prefix, rest = provider_raw.split("/", 1)
        provider_id = _resolve_provider_alias(prefix)
        upstream_model = rest or None
    else:
        provider_id = _resolve_provider_alias(provider_raw)

    # Check provider supports rerank via handler
    rerank_handler = None
    try:
        p = Provider(provider_id)
        rerank_handler = p.handler()
    except (ValueError, ModuleNotFoundError):
        pass

    if rerank_handler is None or not hasattr(rerank_handler, "execute_rerank"):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Rerank provider '{provider_id}' is not supported.",
        )

    # Normalize params
    rerank_params: dict[str, str | int | list | None] = {
        "query": query,
        "documents": documents,
        "top_n": body.get("top_n", 10),
        "return_documents": body.get("return_documents", False),
        "language": body.get("language"),
        "instruct": body.get("instruct"),
        "provider_options": body.get("provider_options"),
    }
    if upstream_model:
        rerank_params["model"] = upstream_model

    request_id: str = str(uuid.uuid4())

    # Find active connection for this provider
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider == provider_id,
            ProviderConnection.is_active.is_(True),
        )
    )
    conn = result.scalars().first()

    # Check if provider needs auth (most do)
    needs_auth = rerank_handler.config.AUTH_HEADER != "" or rerank_handler.config.AUTH_QUERY_PARAM != ""
    if not conn and needs_auth:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No active connection for rerank provider: {provider_id}",
        )

    conn_data: dict = json.loads(conn.data) if conn and conn.data else {}
    api_key: str = conn_data.get("apiKey") or ""

    try:
        proxy = await proxy_for_connection(db, conn, "upstream")
    except ProxyRequiredError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": {"message": str(exc)}},
            headers={"X-Request-Id": request_id},
        )

    start_time: float = time.time()
    try:
        async with create_upstream_client(
            proxy=proxy,
            timeout=60.0,
        ) as client:
            rerank_result: dict = await execute_rerank(
                client, provider_id, rerank_params, api_key, conn_data,
            )
    except httpx.HTTPStatusError as e:
        upstream = (e.response.text or "").strip()[:500]
        if not upstream:
            upstream = (
                f"Upstream HTTP {e.response.status_code} "
                f"(empty body)"
            )
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": {"message": upstream}},
            headers={"X-Request-Id": request_id},
        )
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": str(e)}},
            headers={"X-Request-Id": request_id},
        )
    except httpx.ConnectError as e:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": f"Connection error: {e}"}},
            headers={"X-Request-Id": request_id},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e)[:500]}},
            headers={"X-Request-Id": request_id},
        )

    elapsed_ms: int = int((time.time() - start_time) * 1000)
    rerank_result["metrics"]["response_time_ms"] = elapsed_ms

    usage: dict = rerank_result.get("usage") or {}
    prompt_tokens = int(
        usage.get("total_tokens")
        or usage.get("prompt_tokens")
        or 0
    )
    tracked_model = (
        upstream_model
        or usage.get("model")
        or provider_id
    )
    await save_request_tracking(
        db,
        provider=provider_id,
        model=tracked_model,
        connection_id=str(conn.id) if conn else None,
        endpoint="/v1/rerank",
        prompt_tokens=prompt_tokens,
        completion_tokens=0,
        tokens_json=usage,
        latency_ttft=elapsed_ms,
        latency_total=elapsed_ms,
        request_body=body,
        provider_request_body=rerank_params,
        provider_response_body=rerank_result,
        response_body=rerank_result,
    )

    return JSONResponse(
        status_code=200,
        content=rerank_result,
        headers={"X-Request-Id": request_id},
    )
