"""POST /v1/chat/completions — OpenAI-compatible chat completions proxy."""

import json
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_start, track_request_end
from app.models.provider import ProviderConnection
from sqlalchemy import select

from .shared import _stream_response, _non_stream_response, _should_fallback_on_error, _build_provider_request

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """OpenAI-compatible chat completions proxy.

    Accepts standard OpenAI chat completion requests and routes them
    to the appropriate upstream provider based on model/combo resolution.
    Supports both streaming (SSE) and non-streaming responses.
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

    stream: bool = body.get("stream", False)
    request_id: str = str(uuid.uuid4())

    # Apply combo rotation strategy (per-combo override > global)
    strategy, sticky_limit = await get_combo_strategy(db, combo_name=model)

    # Fallback loop with exclude — retries a new connection on each failure
    exclude_ids: set[str] = set()
    last_error_detail: str | None = None
    last_error_status: int = 503

    while True:
        # Resolve model to upstream targets (combo rotation applied internally)
        targets = await resolve_model_to_targets(
            db, model, stream, exclude_ids=exclude_ids,
            combo_strategy=strategy, combo_sticky_limit=sticky_limit,
        )

        if not targets:
            break

        target = targets[0]
        forward_body: dict = {**body, "model": target.model}
        raw_body: bytes | None = None

        # ── Provider-specific request transform (e.g. Qoder WAF-bypass + COSY) ──
        if target.connection_id:
            conn_result = await db.execute(
                select(ProviderConnection).where(ProviderConnection.id == target.connection_id)
            )
            conn = conn_result.scalar_one_or_none()
            if conn:
                conn_data = json.loads(conn.data) if conn.data else {}
                try:
                    raw_body, signed_headers = await _build_provider_request(target, body, conn_data)
                    if signed_headers:
                        target.headers = signed_headers
                except Exception as e:
                    last_error_detail = f"Provider request build failed: {str(e)}"
                    last_error_status = 500
                    exclude_ids.add(target.connection_id)
                    continue

        try:
            request_start_time: float = time.time()
            active_request_id: str = track_request_start(target.provider, target.model)
            if stream:
                resp = await _stream_response(
                    target, forward_body, request_id,
                    db=db, provider=target.provider, model=target.model,
                    connection_id=target.connection_id,
                    request_body=body, request_start_time=request_start_time,
                    raw_body=raw_body,
                )
            else:
                resp, resp_data = await _non_stream_response(
                    target, forward_body, request_id, raw_body=raw_body,
                )
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            # Success — clear cooldown for this connection
            if target.connection_id:
                await clear_connection_error(db, target.connection_id, model)
                await update_connection_usage(db, target.connection_id)

            if not stream:
                # Non-streaming: track usage immediately (response already received)
                usage: dict = (resp_data or {}).get("usage", {})
                prompt_tokens: int = usage.get("prompt_tokens", 0)
                completion_tokens: int = usage.get("completion_tokens", 0)
                await save_request_tracking(
                    db,
                    provider=target.provider,
                    model=target.model,
                    connection_id=target.connection_id,
                    endpoint="/v1/chat/completions",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    tokens_json=usage,
                    latency_ttft=total_latency_ms,
                    latency_total=total_latency_ms,
                    request_body=body,
                    provider_request_body=forward_body,
                    provider_response_body=resp_data,
                    response_body=resp_data,
                )
            # Streaming: usage tracking happens inside _stream_response generator

            track_request_end(active_request_id)
            return resp

        except httpx.HTTPStatusError as e:
            track_request_end(active_request_id)
            last_error_detail = e.response.text[:500]
            last_error_status = e.response.status_code
            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": last_error_detail}},
                )
            # Cooldown + exclude
            if target.connection_id:
                # Read current backoff level from connection data
                conn_row = await db.execute(
                    select(ProviderConnection).where(ProviderConnection.id == target.connection_id)
                )
                conn_obj = conn_row.scalar_one_or_none()
                current_backoff: int = 0
                if conn_obj and conn_obj.data:
                    current_backoff = json.loads(conn_obj.data).get("backoffLevel", 0)
                cooldown_ms, new_level = calculate_cooldown(
                    e.response.status_code, last_error_detail,
                    backoff_level=current_backoff,
                )
                await mark_connection_unavailable(
                    db, target.connection_id, cooldown_ms, model, new_level,
                )
                exclude_ids.add(target.connection_id)
            continue

        except httpx.ConnectError as e:
            track_request_end(active_request_id)
            last_error_detail = str(e)
            last_error_status = 503
            if target.connection_id:
                exclude_ids.add(target.connection_id)
            continue

        except Exception as e:
            track_request_end(active_request_id)
            last_error_detail = str(e)
            last_error_status = 500
            if target.connection_id:
                exclude_ids.add(target.connection_id)
            continue

    # All targets failed
    error_msg: str = last_error_detail or f"No provider available for model: {model}"
    return JSONResponse(
        status_code=last_error_status,
        content={"error": {"message": error_msg}},
    )
