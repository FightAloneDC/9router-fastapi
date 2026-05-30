"""POST /v1/search — Unified web search proxy."""

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
from app.services.search_adapters import (
    SEARCH_BUILDERS,
    _NOAUTH_SEARCH_PROVIDERS,
    execute_search,
)
from app.services.usage_tracking import save_request_detail, save_request_usage
from app.routers.usage_stream import notify_usage_update
from app.models.provider import ProviderConnection

router = APIRouter()


@router.post("/search")
async def search_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """Unified web search proxy.

    Routes search queries to dedicated search APIs (tavily, brave, serper, etc.)
    and returns normalized results.

    Body:
      - model or provider (required): search provider ID
      - query (required): search query string
      - max_results: max results (default 5)
      - search_type: "web" (default) or "news"
      - country: ISO 3166-1 alpha-2 country code
      - language: ISO 639-1 language code
      - time_range: "day", "week", "month", "year", "any"
      - domain_filter: list of domains (prefix with "-" to exclude)
      - provider_options: provider-specific options

    Response: unified search results format.
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    provider_id: str | None = body.get("model") or body.get("provider")
    query: str | None = body.get("query")

    if not provider_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model or provider",
        )
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: query",
        )

    # Resolve alias
    provider_id = _resolve_provider_alias(provider_id)

    # Check provider is supported
    if provider_id not in SEARCH_BUILDERS:
        supported: list[str] = sorted(SEARCH_BUILDERS.keys())
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Search provider '{provider_id}' is not supported. Supported: {', '.join(supported)}",
        )

    # Normalize params
    search_params: dict[str, str | int | list[str] | None] = {
        "query": query,
        "max_results": body.get("max_results", 5),
        "search_type": body.get("search_type", "web"),
        "country": body.get("country"),
        "language": body.get("language"),
        "time_range": body.get("time_range"),
        "domain_filter": body.get("domain_filter"),
        "provider_options": body.get("provider_options"),
    }

    request_id: str = str(uuid.uuid4())

    # Find active connection for this provider
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider == provider_id,
            ProviderConnection.is_active.is_(True),
        )
    )
    conn = result.scalars().first()

    if not conn and provider_id not in _NOAUTH_SEARCH_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No active connection for search provider: {provider_id}",
        )

    conn_data: dict = json.loads(conn.data) if conn and conn.data else {}
    api_key: str = conn_data.get("apiKey") or ""

    start_time: float = time.time()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_result: dict = await execute_search(
                client, provider_id, search_params, api_key, conn_data,
            )
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=e.response.status_code,
            content={"error": {"message": e.response.text[:500]}},
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
    search_result["metrics"]["response_time_ms"] = elapsed_ms

    # Track usage (search — no token counts)
    await save_request_usage(
        db,
        provider=provider_id,
        model=provider_id,
        connection_id=str(conn.id) if conn else None,
        endpoint="/v1/search",
    )
    notify_usage_update()

    # Save full request detail
    await save_request_detail(
        db,
        provider=provider_id,
        model=provider_id,
        connection_id=str(conn.id) if conn else None,
        status="ok",
        latency_ttft=elapsed_ms,
        latency_total=elapsed_ms,
        request_body=body,
        provider_request_body=search_params,
        provider_response_body=search_result,
        response_body=search_result,
    )

    return JSONResponse(
        status_code=200,
        content=search_result,
        headers={"X-Request-Id": request_id},
    )
