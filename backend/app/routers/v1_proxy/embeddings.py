"""POST /v1/embeddings — OpenAI-compatible embeddings proxy."""

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
from app.services.proxy import (
    resolve_model_to_targets,
    get_combo_strategy,
    clear_connection_error,
    update_connection_usage,
    calculate_cooldown,
    mark_connection_unavailable,
)
from app.services.usage_tracking import save_request_detail, save_request_usage
from app.routers.usage_stream import notify_usage_update
from app.models.provider import ProviderConnection

from .shared import _build_embeddings_url, _build_embeddings_body, _should_fallback_on_error

router = APIRouter()


@router.post("/embeddings")
async def embeddings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """OpenAI-compatible embeddings proxy.

    Accepts standard OpenAI embedding requests and routes them
    to the appropriate upstream provider based on model/combo resolution.
    Supports combo rotation and fallback on upstream failure.
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    model: str | None = body.get("model")
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model",
        )

    if not body.get("input"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: input",
        )

    request_id: str = str(uuid.uuid4())

    # Apply combo rotation strategy (per-combo override > global)
    strategy, sticky_limit = await get_combo_strategy(db, combo_name=model)

    # Fallback loop with exclude
    exclude_ids: set[str] = set()
    last_error_detail: str | None = None
    last_error_status: int = 503

    while True:
        targets = await resolve_model_to_targets(
            db, model, stream=False, exclude_ids=exclude_ids,
            combo_strategy=strategy, combo_sticky_limit=sticky_limit,
        )
        if not targets:
            break

        target = targets[0]
        upstream_url: str = _build_embeddings_url(target)
        forward_body: dict = _build_embeddings_body(target, body)

        try:
            request_start_time: float = time.time()
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    upstream_url,
                    json=forward_body,
                    headers=target.headers,
                )
                if resp.status_code >= 400:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                try:
                    data: dict = resp.json()
                except Exception:
                    data = {"raw": resp.text[:2000]}
                total_latency_ms: int = int((time.time() - request_start_time) * 1000)

                if target.connection_id:
                    await clear_connection_error(db, target.connection_id, model)
                    await update_connection_usage(db, target.connection_id)

                # Track usage
                usage: dict = data.get("usage", {})
                await save_request_usage(
                    db,
                    provider=target.provider,
                    model=target.model,
                    connection_id=target.connection_id,
                    endpoint="/v1/embeddings",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    tokens_json=usage,
                )
                notify_usage_update()

                # Save full request detail
                await save_request_detail(
                    db,
                    provider=target.provider,
                    model=target.model,
                    connection_id=target.connection_id,
                    status="ok",
                    latency_ttft=total_latency_ms,
                    latency_total=total_latency_ms,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    request_body=body,
                    provider_request_body=forward_body,
                    provider_response_body=data,
                    response_body=data,
                )

                return JSONResponse(
                    status_code=resp.status_code,
                    content=data,
                    headers={"X-Request-Id": request_id},
                )

        except httpx.HTTPStatusError as e:
            last_error_detail = e.response.text[:500]
            last_error_status = e.response.status_code
            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": last_error_detail}},
                )
            if target.connection_id:
                conn_row = await db.execute(
                    select(ProviderConnection).where(ProviderConnection.id == target.connection_id)
                )
                conn_obj = conn_row.scalar_one_or_none()
                current_backoff: int = 0
                if conn_obj and conn_obj.data:
                    current_backoff = json.loads(conn_obj.data).get("backoffLevel", 0)
                cooldown_ms, new_level = calculate_cooldown(
                    e.response.status_code, last_error_detail, backoff_level=current_backoff,
                )
                await mark_connection_unavailable(
                    db, target.connection_id, cooldown_ms, model, new_level,
                )
                exclude_ids.add(target.connection_id)
            continue
        except httpx.ConnectError as e:
            last_error_detail = str(e)
            last_error_status = 503
            if target.connection_id:
                exclude_ids.add(target.connection_id)
            continue
        except Exception as e:
            last_error_detail = str(e)
            last_error_status = 500
            if target.connection_id:
                exclude_ids.add(target.connection_id)
            continue

    error_msg: str = last_error_detail or f"No provider available for model: {model}"
    return JSONResponse(
        status_code=last_error_status,
        content={"error": {"message": error_msg}},
    )
