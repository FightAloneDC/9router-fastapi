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
)
from app.services.responses_translator import (
    responses_to_chat_completions,
    chat_completions_to_responses,
    ResponsesStreamTranslator,
    build_incomplete_terminal_sse,
)
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_start, track_request_end
from app.models.provider import ProviderConnection

from .shared import (
    _should_fallback_on_error,
    _build_provider_request,
    _unwrap_qoder_sse_line,
    _maybe_refresh_on_auth_error,
    _mark_conn_failed,
)

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
    refreshed_ids: set[str] = set()
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

        # ── FORMAT=openai-responses upstream (Grok CLI): passthrough ──
        is_responses_upstream: bool = False
        provider_obj = None
        try:
            from app.providers.provider import Provider
            provider_obj = Provider(target.provider)
            is_responses_upstream = (
                provider_obj.config().FORMAT == "openai-responses"
            )
        except (ValueError, ModuleNotFoundError):
            pass

        raw_body: bytes | None = None
        if is_responses_upstream:
            # Client already speaks Responses API — forward natively
            forward_body: dict = {**body, "model": target.model}
            if target.connection_id and provider_obj is not None:
                conn = await db.get(
                    ProviderConnection, uuid.UUID(target.connection_id),
                )
                if conn:
                    conn_data = json.loads(conn.data) if conn.data else {}
                    handler = provider_obj.handler()
                    raw_body, signed_headers = (
                        await handler.build_request_body(
                            target.model, body, conn_data,
                        )
                    )
                    if signed_headers:
                        target.headers = signed_headers
        else:
            # Translate to Chat Completions for non-Responses upstreams
            forward_body = {
                **chat_body, "model": target.model, "stream": stream,
            }
            # Provider-specific encoding (e.g. Qoder COSY) — same as chat
            if target.connection_id:
                conn = await db.get(
                    ProviderConnection, uuid.UUID(target.connection_id),
                )
                if conn:
                    conn_data = json.loads(conn.data) if conn.data else {}
                    try:
                        raw_body, signed_headers = (
                            await _build_provider_request(
                                target, forward_body, conn_data,
                            )
                        )
                        if signed_headers:
                            target.headers = signed_headers
                    except Exception as e:
                        conn_id = target.connection_id
                        if (
                            conn_id
                            and conn_id not in refreshed_ids
                            and await _maybe_refresh_on_auth_error(
                                target, db,
                            )
                        ):
                            refreshed_ids.add(conn_id)
                            continue
                        last_error_detail = (
                            f"Provider request build failed: {str(e)}"
                        )
                        last_error_status = 500
                        exclude_ids.add(conn_id)
                        continue

        try:
            request_start_time: float = time.time()
            active_request_id: str = track_request_start(target.provider, target.model)
            if stream:
                if is_responses_upstream:
                    resp = await _stream_responses_passthrough(
                        target, forward_body, request_id, model,
                        db=db, provider=target.provider,
                        connection_id=target.connection_id,
                        request_body=body,
                        request_start_time=request_start_time,
                        raw_body=raw_body,
                        active_request_id=active_request_id,
                    )
                else:
                    resp = await _stream_responses(
                        target, forward_body, request_id, model,
                        db=db, provider=target.provider,
                        connection_id=target.connection_id,
                        request_body=body,
                        request_start_time=request_start_time,
                        raw_body=raw_body,
                        active_request_id=active_request_id,
                    )
                resp_data: dict = {}
            else:
                if is_responses_upstream:
                    resp, resp_data = (
                        await _non_stream_responses_passthrough(
                            target, forward_body, request_id,
                            raw_body=raw_body,
                        )
                    )
                else:
                    resp, resp_data = await _non_stream_responses(
                        target, forward_body, request_id, model,
                        raw_body=raw_body,
                    )
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
            # and track_request_end is called inside the generator when stream finishes.
            # For non-streaming: end tracking here after response is received.
            if not stream:
                track_request_end(active_request_id)

            return resp

        except httpx.HTTPStatusError as e:
            track_request_end(active_request_id, status="error")
            last_error_detail = e.response.text[:500]
            last_error_status = e.response.status_code

            # Auth-token refresh via provider handler on 401/403
            conn_id = target.connection_id
            if (
                conn_id
                and conn_id not in refreshed_ids
                and await _maybe_refresh_on_auth_error(
                    target, db, e.response.status_code,
                )
            ):
                refreshed_ids.add(conn_id)
                continue

            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": last_error_detail}},
                    headers={"X-Request-Id": request_id},
                )
            await _mark_conn_failed(
                db, target.connection_id, e.response.status_code,
                last_error_detail, model, exclude_ids,
            )
            continue
        except httpx.ConnectError as e:
            track_request_end(active_request_id, status="error")
            last_error_detail = str(e)
            last_error_status = 503
            if target.connection_id:
                exclude_ids.add(target.connection_id)
            continue
        except Exception as e:
            track_request_end(active_request_id, status="error")
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
    *, raw_body: bytes | None = None,
) -> tuple[JSONResponse, dict]:
    """Non-streaming: translate response to Responses API format.

    Returns (JSONResponse, raw_chat_data) so callers can extract usage info.
    """
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(target.url, **send_kwargs)
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
    raw_body: bytes | None = None,
    active_request_id: str | None = None,
) -> StreamingResponse:
    """Streaming: translate Chat Completions SSE to Responses API SSE."""
    translator = ResponsesStreamTranslator(model=model)
    is_qoder = provider == "qoder"
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}

        def _handle_chat_sse_line(line: str) -> list[str]:
            nonlocal usage
            out: list[str] = []
            line = line.strip()
            if not line.startswith("data: "):
                return out
            data_str: str = line[6:]
            if data_str == "[DONE]":
                for event in translator.finalize(usage):
                    out.append(
                        f"event: {event['event']}\n"
                        f"data: {json.dumps(event['data'])}\n\n"
                    )
                return out
            try:
                chunk_data: dict = json.loads(data_str)
            except json.JSONDecodeError:
                return out
            if "usage" in chunk_data and chunk_data["usage"]:
                usage = chunk_data["usage"]
            events = translator.translate_chunk(chunk_data)
            for event in events:
                out.append(
                    f"event: {event['event']}\n"
                    f"data: {json.dumps(event['data'])}\n\n"
                )
            return out

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST", target.url, **send_kwargs,
                ) as resp:
                    resp.raise_for_status()
                    if is_qoder:
                        qoder_buf = b""
                        async for chunk in resp.aiter_bytes():
                            qoder_buf += chunk
                            while b"\n" in qoder_buf:
                                line_b, qoder_buf = qoder_buf.split(
                                    b"\n", 1,
                                )
                                line = line_b.decode(
                                    "utf-8", errors="ignore",
                                )
                                unwrapped = _unwrap_qoder_sse_line(line)
                                if not unwrapped:
                                    continue
                                for piece in _handle_chat_sse_line(
                                    unwrapped,
                                ):
                                    yield piece
                        if qoder_buf:
                            line = qoder_buf.decode(
                                "utf-8", errors="ignore",
                            )
                            unwrapped = _unwrap_qoder_sse_line(line)
                            if unwrapped:
                                for piece in _handle_chat_sse_line(
                                    unwrapped,
                                ):
                                    yield piece
                    else:
                        buffer = ""
                        async for chunk in resp.aiter_text():
                            buffer += chunk
                            while "\n" in buffer:
                                line, buffer = buffer.split("\n", 1)
                                for piece in _handle_chat_sse_line(line):
                                    yield piece
                    for event in translator.finalize(usage):
                        yield (
                            f"event: {event['event']}\n"
                            f"data: {json.dumps(event['data'])}\n\n"
                        )
            except Exception as e:
                yield (
                    f"event: error\n"
                    f"data: {json.dumps({'message': str(e)})}\n\n"
                )
                for event in translator.finalize(usage):
                    yield (
                        f"event: {event['event']}\n"
                        f"data: {json.dumps(event['data'])}\n\n"
                    )

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

        # End active request tracking when stream finishes
        if active_request_id:
            track_request_end(active_request_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Request-Id": request_id},
    )


async def _non_stream_responses_passthrough(
    target: object, body: dict, request_id: str,
    raw_body: bytes | None = None,
) -> tuple[JSONResponse, dict]:
    """Non-streaming passthrough to a native Responses-API upstream.

    The upstream forces streaming, so the SSE is consumed internally and
    the response.completed object is returned to the client as-is.
    """
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    completed: dict = {}
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST", target.url, **send_kwargs,
        ) as resp:
            resp.raise_for_status()
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict) and (
                        event.get("type") == "response.completed"
                    ):
                        completed = event.get("response") or {}

    if not completed:
        completed = {
            "id": request_id,
            "object": "response",
            "status": "completed",
            "output": [],
        }

    # Usage tracking expects Chat Completions keys
    usage = completed.get("usage", {}) or {}
    tracking_data = dict(completed)
    tracking_data["usage"] = {
        "prompt_tokens": usage.get("input_tokens", 0),
        "completion_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get(
            "total_tokens",
            usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        ),
    }
    return JSONResponse(
        status_code=200,
        content=completed,
        headers={"X-Request-Id": request_id},
    ), tracking_data


async def _stream_responses_passthrough(
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
    raw_body: bytes | None = None,
    active_request_id: str | None = None,
) -> StreamingResponse:
    """Streaming passthrough: forward Responses API SSE events as-is."""
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}
        saw_terminal = False
        terminal_types = {
            "response.completed",
            "response.failed",
            "response.incomplete",
            "response.cancelled",
        }
        response_id = f"resp_{request_id}"
        # Buffer SSE lines — terminal JSON often spans TCP chunks, so
        # splitting only on the current chunk misses response.completed
        # and wrongly appends response.incomplete afterward.
        line_buf = ""

        def _observe_sse_line(line: str) -> None:
            nonlocal saw_terminal, response_id, usage
            line = line.strip()
            if not line.startswith("data:"):
                return
            data_str = line[5:].strip()
            if not data_str or data_str == "[DONE]":
                return
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                return
            if not isinstance(event, dict):
                return
            event_type = event.get("type")
            if event_type in terminal_types:
                saw_terminal = True
            if event_type == "response.completed":
                resp_obj = event.get("response") or {}
                if resp_obj.get("id"):
                    response_id = resp_obj["id"]
                u = resp_obj.get("usage") or {}
                if u:
                    usage = {
                        "prompt_tokens": u.get("input_tokens", 0),
                        "completion_tokens": u.get(
                            "output_tokens", 0,
                        ),
                        "total_tokens": u.get("total_tokens", 0),
                    }
            elif event_type == "response.created":
                resp_obj = event.get("response") or {}
                if resp_obj.get("id"):
                    response_id = resp_obj["id"]

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST", target.url, **send_kwargs,
                ) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_text():
                        yield chunk
                        line_buf += chunk
                        while "\n" in line_buf:
                            line, line_buf = line_buf.split("\n", 1)
                            _observe_sse_line(line)
                    if line_buf.strip():
                        _observe_sse_line(line_buf)
                if not saw_terminal:
                    yield build_incomplete_terminal_sse(
                        response_id=response_id,
                        model=model,
                    )
            except Exception as e:
                yield (
                    "event: error\n"
                    f"data: {json.dumps({'message': str(e)})}\n\n"
                )
                if not saw_terminal:
                    yield build_incomplete_terminal_sse(
                        response_id=response_id,
                        model=model,
                    )

        # Save usage tracking after stream consumed
        if db and provider and request_start_time:
            try:
                from app.database import async_session
                async with async_session() as tracking_db:
                    total_latency_ms = int(
                        (time.time() - request_start_time) * 1000
                    )
                    await save_request_tracking(
                        tracking_db,
                        provider=provider,
                        model=model,
                        connection_id=connection_id,
                        endpoint="/v1/responses",
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get(
                            "completion_tokens", 0,
                        ),
                        tokens_json=usage,
                        latency_ttft=total_latency_ms,
                        latency_total=total_latency_ms,
                        request_body=request_body,
                        provider_request_body=body,
                        provider_response_body={
                            "_note": (
                                "Streaming response — raw not captured"
                            ),
                        },
                        response_body={"_note": "Streaming response"},
                    )
            except Exception as e:
                print(
                    f"[RESPONSES PASSTHROUGH TRACKING ERROR] {e}",
                    flush=True,
                )

        # End active request tracking when stream finishes
        if active_request_id:
            track_request_end(active_request_id)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
        },
    )
