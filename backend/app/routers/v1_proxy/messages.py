"""POST /v1/messages — Claude Messages API compatible proxy."""

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
from app.services.message_translator import (
    claude_to_openai_request,
    openai_to_claude_response,
    ClaudeStreamTranslator,
)
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_start, track_request_end
from app.models.provider import ProviderConnection

from .shared import _should_fallback_on_error

router = APIRouter()


@router.post("/messages")
async def messages_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """Claude Messages API compatible proxy.

    Accepts Anthropic Messages API format and routes to the appropriate
    upstream provider. For Claude-format providers, the request is forwarded
    as-is. For OpenAI-format providers, the request is automatically
    translated between Claude and OpenAI formats.

    Body (Claude Messages API spec):
      - model (required): "provider/model" or just model name
      - max_tokens (required): max tokens to generate
      - messages (required): conversation messages
      - system: system prompt (string or content blocks)
      - temperature, top_p, top_k, stop_sequences, stream: optional

    Response: Claude Messages API format ``{"id", "type", "message", ...}``
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    model_str: str | None = body.get("model")
    max_tokens: int | None = body.get("max_tokens")
    messages: list | None = body.get("messages")

    if not model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model",
        )
    if max_tokens is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: max_tokens",
        )
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: messages",
        )

    request_id: str = str(uuid.uuid4())
    is_stream: bool = body.get("stream", False)

    # Apply combo rotation strategy (per-combo override > global)
    strategy, sticky_limit = await get_combo_strategy(db, combo_name=model_str)

    # Fallback loop with exclude
    exclude_ids: set[str] = set()
    last_error_detail: str | None = None
    last_error_status: int = 503

    while True:
        targets = await resolve_model_to_targets(
            db, model_str, is_stream, exclude_ids=exclude_ids,
            combo_strategy=strategy, combo_sticky_limit=sticky_limit,
        )
        if not targets:
            break

        target = targets[0]

        # Determine if the upstream is Claude-format or OpenAI-format
        is_claude_upstream: bool = False
        try:
            from app.providers.provider import Provider
            p = Provider(target.provider)
            c = p.config()
            is_claude_upstream = c.FORMAT == "claude"
        except (ValueError, ModuleNotFoundError):
            pass

        # Prepare the request body for the upstream
        if is_claude_upstream:
            forward_body: dict = {**body, "model": target.model}
        else:
            forward_body = claude_to_openai_request(body)
            forward_body["model"] = target.model
            forward_body["stream"] = is_stream

        try:
            request_start_time: float = time.time()
            active_request_id: str = track_request_start(target.provider, target.model)
            if is_stream:
                resp = await _messages_stream_response(
                    target, forward_body, request_id,
                    is_claude_upstream=is_claude_upstream,
                    model_str=model_str,
                    db=db, provider=target.provider, model=target.model,
                    connection_id=target.connection_id,
                    request_body=body, request_start_time=request_start_time,
                )
                resp_data: dict = {}
            else:
                async with httpx.AsyncClient(timeout=300.0) as client:
                    http_resp = await client.post(
                        target.url,
                        json=forward_body,
                        headers=target.headers,
                    )
                    http_resp.raise_for_status()
                    resp_data = http_resp.json()

                if is_claude_upstream:
                    resp = JSONResponse(
                        status_code=200,
                        content=resp_data,
                        headers={"X-Request-Id": request_id},
                    )
                else:
                    claude_resp = openai_to_claude_response(
                        resp_data,
                        model=model_str,
                        request_id=request_id,
                    )
                    resp = JSONResponse(
                        status_code=200,
                        content=claude_resp,
                        headers={"X-Request-Id": request_id},
                    )
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            # Success — clear cooldown
            if target.connection_id:
                await clear_connection_error(db, target.connection_id, model_str)
                await update_connection_usage(db, target.connection_id)

            if not is_stream:
                # Non-streaming: track usage immediately
                usage: dict = (resp_data or {}).get("usage", {})
                prompt_tokens: int = usage.get("prompt_tokens", usage.get("input_tokens", 0))
                completion_tokens: int = usage.get("completion_tokens", usage.get("output_tokens", 0))
                await save_request_tracking(
                    db,
                    provider=target.provider,
                    model=target.model,
                    connection_id=target.connection_id,
                    endpoint="/v1/messages",
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
            # Streaming: usage tracking happens inside _messages_stream_response generator

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
                try:
                    error_body = e.response.json()
                except Exception:
                    error_body = {"error": {"message": last_error_detail}}
                if is_claude_upstream:
                    return JSONResponse(
                        status_code=e.response.status_code,
                        content=error_body,
                        headers={"X-Request-Id": request_id},
                    )
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={
                        "type": "error",
                        "error": {"type": "api_error", "message": last_error_detail},
                    },
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
                    db, target.connection_id, cooldown_ms, model_str, new_level,
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

    error_msg: str = last_error_detail or f"No provider available for model: {model_str}"
    return JSONResponse(
        status_code=last_error_status,
        content={
            "type": "error",
            "error": {"type": "api_error", "message": error_msg},
        },
        headers={"X-Request-Id": request_id},
    )


async def _messages_stream_response(
    target: object,
    body: dict,
    request_id: str,
    *,
    is_claude_upstream: bool,
    model_str: str,
    db: AsyncSession | None = None,
    provider: str | None = None,
    model: str | None = None,
    connection_id: str | None = None,
    request_body: dict | None = None,
    request_start_time: float | None = None,
) -> StreamingResponse:
    """Stream response for /v1/messages endpoint.

    For Claude-format upstream: pass through SSE bytes as-is.
    For OpenAI-format upstream: translate OpenAI SSE → Claude SSE.
    """

    # Shared mutable dict — generators populate it as stream is consumed
    usage_ref: dict[str, dict] = {"usage": {}}

    async def generate_claude_passthrough():  # type: ignore[no-untyped-def]
        """Forward Claude SSE bytes directly."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST", target.url, json=body, headers=target.headers,
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                        # Parse SSE to capture usage from Claude-format events
                        try:
                            text = chunk.decode("utf-8", errors="ignore")
                            for line in text.split("\n"):
                                if line.startswith("data: ") and line.strip() != "data: [DONE]":
                                    data = json.loads(line[6:])
                                    if "usage" in data and data["usage"]:
                                        usage_ref["usage"] = data["usage"]
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
            except httpx.HTTPStatusError as e:
                error_data = json.dumps({
                    "type": "error",
                    "error": {"type": "api_error", "message": f"Upstream error: {e.response.status_code}"},
                })
                yield f"event: error\ndata: {error_data}\n\n".encode()
            except Exception as e:
                error_data = json.dumps({
                    "type": "error",
                    "error": {"type": "api_error", "message": f"Proxy error: {str(e)}"},
                })
                yield f"event: error\ndata: {error_data}\n\n".encode()

    async def generate_openai_to_claude():  # type: ignore[no-untyped-def]
        """Translate OpenAI SSE → Claude SSE."""
        translator = ClaudeStreamTranslator(model=model_str, request_id=request_id)
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST", target.url, json=body, headers=target.headers,
                ) as resp:
                    resp.raise_for_status()
                    buffer = ""
                    async for chunk in resp.aiter_text():
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line:
                                continue
                            # Parse SSE to capture usage from OpenAI-format chunks
                            if line.startswith("data: ") and line.strip() != "data: [DONE]":
                                try:
                                    data = json.loads(line[6:])
                                    if "usage" in data and data["usage"]:
                                        usage_ref["usage"] = data["usage"]
                                except (json.JSONDecodeError, UnicodeDecodeError):
                                    pass
                            claude_events = translator.feed(line)
                            for event in claude_events:
                                yield event.encode()
                    # Process remaining buffer
                    if buffer.strip():
                        claude_events = translator.feed(buffer.strip())
                        for event in claude_events:
                            yield event.encode()
                    # Force finish if not already done
                    finish_events = translator._finish()
                    for event in finish_events:
                        yield event.encode()
            except httpx.HTTPStatusError as e:
                error_data = json.dumps({
                    "type": "error",
                    "error": {"type": "api_error", "message": f"Upstream error: {e.response.status_code}"},
                })
                yield f"event: error\ndata: {error_data}\n\n".encode()
            except Exception as e:
                error_data = json.dumps({
                    "type": "error",
                    "error": {"type": "api_error", "message": f"Proxy error: {str(e)}"},
                })
                yield f"event: error\ndata: {error_data}\n\n".encode()

    if is_claude_upstream:
        generator = generate_claude_passthrough()
    else:
        generator = generate_openai_to_claude()

    # Wrap to save tracking after stream is consumed
    async def tracked_generate():  # type: ignore[no-untyped-def]
        async for chunk in generator:
            yield chunk
        # After stream consumed, save usage tracking
        if db and provider and request_start_time:
            try:
                from app.database import async_session
                async with async_session() as tracking_db:
                    total_latency_ms = int((time.time() - request_start_time) * 1000)
                    usage = usage_ref["usage"]
                    prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
                    completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
                    await save_request_tracking(
                        tracking_db,
                        provider=provider,
                        model=model,
                        connection_id=connection_id,
                        endpoint="/v1/messages",
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
                print(f"[MESSAGES STREAM TRACKING ERROR] {e}", flush=True)

    return StreamingResponse(
        tracked_generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
        },
    )
