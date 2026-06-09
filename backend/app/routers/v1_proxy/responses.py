"""POST /v1/responses — OpenAI Responses API compatible proxy."""

import json
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
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
from app.services.responses_translator import (
    responses_to_chat_completions,
    chat_completions_to_responses,
    ResponsesStreamTranslator,
)
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_start, track_request_end
from app.models.provider import ProviderConnection

from .shared import _should_fallback_on_error

router = APIRouter()


@router.post("/responses")
async def responses_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """OpenAI Responses API compatible proxy.

    Accepts Responses API format and translates to/from Chat Completions
    for upstream providers. Supports both streaming and non-streaming.

    Body (OpenAI Responses API spec):
      - model (required): model name (e.g. "openai/gpt-4o-mini")
      - input (required): string or array of input items
      - instructions: system prompt (optional)
      - stream: enable streaming (optional, default false)
      - tools, temperature, max_output_tokens, etc.: optional

    Response: Responses API format ``{"id", "object": "response", "output": [...]}``
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

    # Translate Responses API → Chat Completions
    chat_body: dict = responses_to_chat_completions(body)

    # Apply combo rotation strategy (per-combo override > global)
    strategy, sticky_limit = await get_combo_strategy(db, combo_name=model)

    # Fallback loop with exclude
    exclude_ids: set[str] = set()
    last_error_detail: str | None = None
    last_error_status: int = 503

    while True:
        targets = await resolve_model_to_targets(
            db, model, stream, exclude_ids=exclude_ids,
            combo_strategy=strategy, combo_sticky_limit=sticky_limit,
        )
        if not targets:
            break

        target = targets[0]
        forward_body: dict = {**chat_body, "model": target.model, "stream": stream}

        try:
            request_start_time: float = time.time()
            active_request_id: str = track_request_start(target.provider, target.model)
            if stream:
                resp = await _stream_responses(
                    target, forward_body, request_id, model,
                    db=db, provider=target.provider,
                    connection_id=target.connection_id,
                    request_body=body, request_start_time=request_start_time,
                )
                resp_data: dict = {}
            else:
                resp, resp_data = await _non_stream_responses(target, forward_body, request_id, model)
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            if target.connection_id:
                await clear_connection_error(db, target.connection_id, model)
                await update_connection_usage(db, target.connection_id)

            if not stream:
                # Non-streaming: track usage immediately
                usage: dict = (resp_data or {}).get("usage", {})
                prompt_tokens: int = usage.get("prompt_tokens", 0)
                completion_tokens: int = usage.get("completion_tokens", 0)
                await save_request_tracking(
                    db,
                    provider=target.provider,
                    model=target.model,
                    connection_id=target.connection_id,
                    endpoint="/v1/responses",
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
            # Streaming: usage tracking happens inside _stream_responses generator

            track_request_end(active_request_id)
            return resp

        except httpx.HTTPStatusError as e:
            track_request_end(active_request_id)
            last_error_detail = e.response.text[:500]
            last_error_status = e.response.status_code

            # ── Qoder auto-refresh on 401/403 ──
            if e.response.status_code in (401, 403):
                from app.routers.v1_proxy.shared import _try_qoder_token_refresh
                if await _try_qoder_token_refresh(target, db):
                    continue

            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": last_error_detail}},
                    headers={"X-Request-Id": request_id},
                )
            if target.connection_id:
                current_backoff: int = 0
                conn_obj = await db.get(ProviderConnection, uuid.UUID(target.connection_id))
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

    error_msg: str = last_error_detail or "All providers failed"
    return JSONResponse(
        status_code=last_error_status,
        content={"error": {"message": error_msg}},
        headers={"X-Request-Id": request_id},
    )


async def _non_stream_responses(
    target: object, body: dict, request_id: str, model: str,
) -> tuple[JSONResponse, dict]:
    """Non-streaming: translate response to Responses API format.

    Returns (JSONResponse, raw_chat_data) so callers can extract usage info.
    """
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(target.url, json=body, headers=target.headers)
        resp.raise_for_status()
        data: dict = resp.json()

    result: dict = chat_completions_to_responses(data, model)
    return JSONResponse(status_code=200, content=result, headers={"X-Request-Id": request_id}), data


async def _stream_responses(
    target: object,
    body: dict,
    request_id: str,
    model: str,
    *,
    db: AsyncSession | None = None,
    provider: str | None = None,
    connection_id: str | None = None,
    request_body: dict | None = None,
    request_start_time: float | None = None,
) -> StreamingResponse:
    """Streaming: translate Chat Completions SSE to Responses API SSE."""
    translator = ResponsesStreamTranslator(model=model)

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream("POST", target.url, json=body, headers=target.headers) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            data_str: str = line[6:]
                            if data_str == "[DONE]":
                                continue
                            try:
                                chunk_data: dict = json.loads(data_str)
                                # Capture usage from SSE chunks
                                if "usage" in chunk_data and chunk_data["usage"]:
                                    usage = chunk_data["usage"]
                                events = translator.translate_chunk(chunk_data)
                                for event in events:
                                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

        # Save usage tracking after stream consumed
        if db and provider and request_start_time:
            try:
                from app.database import async_session
                async with async_session() as tracking_db:
                    total_latency_ms = int((time.time() - request_start_time) * 1000)
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    await save_request_tracking(
                        tracking_db,
                        provider=provider,
                        model=model,
                        connection_id=connection_id,
                        endpoint="/v1/responses",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        tokens_json=usage,
                        latency_ttft=total_latency_ms,
                        latency_total=total_latency_ms,
                        request_body=request_body,
                        provider_request_body=body,
                        provider_response_body={"_note": "Streaming response — raw not captured"},
                        response_body={"_note": "Streaming response"},
                    )
            except Exception as e:
                print(f"[RESPONSES STREAM TRACKING ERROR] {e}", flush=True)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Request-Id": request_id},
    )
