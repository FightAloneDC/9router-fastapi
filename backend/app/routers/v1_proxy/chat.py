"""POST /v1/chat/completions — OpenAI-compatible chat completions proxy."""

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
from app.services.quota import observe_upstream_response
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_start, track_request_end
from app.services.outbound_proxy import (
    ProxyRequiredError,
    create_upstream_client,
    proxy_for_connection,
    purpose_from_header,
)
from app.models.provider import ProviderConnection
from sqlalchemy import select

from app.services.message_translator import (
    openai_to_claude_request,
    OpenaiStreamTranslator,
)
from .shared import (
    _stream_response,
    _non_stream_response,
    _should_fallback_on_error,
    _build_provider_request,
    _maybe_refresh_on_auth_error,
    _mark_conn_failed,
)

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
    purpose = purpose_from_header(request.headers.get("x-9router-purpose"))

    # Apply combo rotation strategy (per-combo override > global)
    strategy, sticky_limit = await get_combo_strategy(db, combo_name=model)

    # Fallback loop with exclude — retries a new connection on each failure
    exclude_ids: set[str] = set()
    refreshed_ids: set[str] = set()
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
        proxy: str | None = None

        # ── FORMAT=claude / openai-responses: translated upstreams ──
        is_claude_upstream: bool = False
        is_responses_upstream: bool = False
        try:
            from app.providers.provider import Provider
            p = Provider(target.provider)
            c = p.config()
            is_claude_upstream = c.FORMAT == "claude"
            is_responses_upstream = c.FORMAT == "openai-responses"
        except (ValueError, ModuleNotFoundError):
            pass

        if is_claude_upstream:
            forward_body = openai_to_claude_request(forward_body)

        # ── Provider-specific request transform (e.g. Qoder WAF-bypass + COSY) ──
        if target.connection_id:
            conn_result = await db.execute(
                select(ProviderConnection).where(ProviderConnection.id == target.connection_id)
            )
            conn = conn_result.scalar_one_or_none()
            if conn:
                conn_data = json.loads(conn.data) if conn.data else {}
                try:
                    proxy = await proxy_for_connection(db, conn, purpose)
                except ProxyRequiredError as exc:
                    return JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"error": {"message": str(exc)}},
                    )
                try:
                    raw_body, signed_headers = await _build_provider_request(target, body, conn_data)
                    if signed_headers:
                        target.headers = signed_headers
                except Exception as e:
                    # Auth-token refresh once per connection, then retry
                    conn_id = target.connection_id
                    if (
                        conn_id
                        and conn_id not in refreshed_ids
                        and await _maybe_refresh_on_auth_error(target, db)
                    ):
                        refreshed_ids.add(conn_id)
                        continue
                    last_error_detail = f"Provider request build failed: {str(e)}"
                    last_error_status = 500
                    exclude_ids.add(conn_id)
                    continue

        try:
            request_start_time: float = time.time()
            active_request_id: str = track_request_start(target.provider, target.model)
            if stream:
                if is_claude_upstream:
                    resp = await _stream_claude_response(
                        target, forward_body, request_id,
                        db=db, provider=target.provider,
                        model=target.model,
                        connection_id=target.connection_id,
                        request_body=body,
                        request_start_time=request_start_time,
                        active_request_id=active_request_id,
                        proxy=proxy,
                    )
                elif is_responses_upstream:
                    resp = await _stream_grok_responses(
                        target, forward_body, request_id,
                        db=db, provider=target.provider,
                        model=target.model,
                        connection_id=target.connection_id,
                        request_body=body,
                        request_start_time=request_start_time,
                        raw_body=raw_body,
                        active_request_id=active_request_id,
                        proxy=proxy,
                    )
                else:
                    resp = await _stream_response(
                        target, forward_body, request_id,
                        db=db, provider=target.provider,
                        model=target.model,
                        connection_id=target.connection_id,
                        request_body=body,
                        request_start_time=request_start_time,
                        raw_body=raw_body,
                        active_request_id=active_request_id,
                        proxy=proxy,
                    )
            else:
                if is_claude_upstream:
                    resp, resp_data = await _non_stream_claude(
                        target, forward_body, request_id,
                        proxy=proxy,
                    )
                elif is_responses_upstream:
                    resp, resp_data = await _non_stream_grok_responses(
                        target, forward_body, request_id,
                        raw_body=raw_body, db=db,
                        proxy=proxy,
                    )
                else:
                    resp, resp_data = await _non_stream_response(
                        target, forward_body, request_id,
                        raw_body=raw_body,
                        proxy=proxy,
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
                )
            # 503: transient upstream — exclude this conn, no cooldown
            if e.response.status_code == 503:
                if target.connection_id:
                    exclude_ids.add(target.connection_id)
                continue
            # Cooldown + exclude
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

    # All targets failed
    error_msg: str = last_error_detail or f"No provider available for model: {model}"
    return JSONResponse(
        status_code=last_error_status,
        content={"error": {"message": error_msg}},
    )


# ─────────────────────────────────────────────────────────────────────
# Claude-format upstream helpers (Anthropic ↔ OpenAI translation)
# ─────────────────────────────────────────────────────────────────────


async def _non_stream_claude(
    target,
    body: dict,
    request_id: str,
    *,
    proxy: str | None = None,
) -> tuple[JSONResponse, dict]:
    """Non-streaming call to FORMAT=claude upstream.

    Many Anthropic APIs are streaming-only, so we stream internally,
    collect text deltas, and return a single OpenAI JSON response.
    """
    from app.services.message_translator import (
        OpenaiStreamTranslator,
    )

    translator = OpenaiStreamTranslator(
        model=body.get("model", ""),
        request_id=request_id,
    )
    content_parts: list[str] = []
    usage_data: dict = {}
    finish_reason: str = "stop"

    async with create_upstream_client(proxy=proxy, timeout=300.0) as client:
        async with client.stream(
            "POST",
            target.url,
            json=body,
            headers=target.headers,
        ) as resp:
            if resp.status_code >= 400:
                err = (await resp.aread()).decode(
                    "utf-8", errors="ignore"
                )
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp,
                    response=resp,
                )
            buf = b""
            async for chunk in resp.aiter_bytes():
                buf += chunk
                while b"\n" in buf:
                    lb, buf = buf.split(b"\n", 1)
                    try:
                        ln = lb.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
                    for ev in translator.feed(ln):
                        if ev.startswith("data: [DONE]"):
                            continue
                        if ev.startswith("data: {"):
                            try:
                                p = json.loads(ev[6:].strip())
                                choices = p.get("choices", [])
                                for c in choices:
                                    d = c.get("delta", {})
                                    if d.get("content"):
                                        content_parts.append(
                                            d["content"]
                                        )
                                    if c.get("finish_reason"):
                                        finish_reason = (
                                            c["finish_reason"]
                                        )
                                if p.get("usage"):
                                    usage_data = p["usage"]
                            except Exception:
                                pass
    pin = usage_data.get("prompt_tokens", 0)
    pout = usage_data.get("completion_tokens", 0)

    translated = {
        "id": request_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", ""),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "".join(content_parts),
            },
            "finish_reason": finish_reason,
        }],
        "usage": {
            "prompt_tokens": pin,
            "completion_tokens": pout,
            "total_tokens": pin + pout,
        },
    }
    return JSONResponse(
        status_code=200,
        content=translated,
        headers={"X-Request-Id": request_id},
    ), translated


async def _stream_claude_response(
    target,
    body: dict,
    request_id: str,
    db=None,
    provider: str = "",
    model: str = "",
    connection_id: str | None = None,
    request_body: dict | None = None,
    request_start_time: float | None = None,
    active_request_id: str | None = None,
    proxy: str | None = None,
) -> StreamingResponse:
    """Streaming call to FORMAT=claude upstream.

    No pre-flight. Translates Anthropic SSE → OpenAI SSE.
    503 errors are NOT rate-limited (transient upstream issue).
    """
    from fastapi.responses import StreamingResponse

    translator = OpenaiStreamTranslator(
        model=body.get("model", ""),
        request_id=request_id,
    )
    send_kwargs: dict = {
        "headers": target.headers,
        "json": body,
    }

    async def generate():
        usage: dict = {}
        async with create_upstream_client(
            proxy=proxy,
            timeout=300.0,
        ) as client:
            try:
                async with client.stream(
                    "POST",
                    target.url,
                    **send_kwargs,
                ) as resp:
                    if resp.status_code >= 400:
                        err = await resp.aread()
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp,
                            response=resp,
                        )
                    buffer = b""
                    async for chunk in resp.aiter_bytes():
                        buffer += chunk
                        while b"\n" in buffer:
                            line_bytes, buffer = buffer.split(
                                b"\n", 1
                            )
                            try:
                                line = line_bytes.decode(
                                    "utf-8", errors="ignore"
                                )
                            except Exception:
                                continue
                            for ev in translator.feed(line):
                                yield ev.encode()
                                try:
                                    if ev.strip(
                                    ).startswith("data:"):
                                        d = json.loads(
                                            ev[6:].strip()
                                        )
                                        if d.get("usage"):
                                            usage = d["usage"]
                                except Exception:
                                    pass
                    if buffer:
                        try:
                            line = buffer.decode(
                                "utf-8", errors="ignore"
                            )
                        except Exception:
                            line = ""
                        for ev in translator.feed(line):
                            yield ev.encode()
            except httpx.HTTPStatusError:
                raise
            except Exception:
                raise

        if db and provider and model:
            from app.services.usage_tracking import (
                save_request_tracking,
            )
            await save_request_tracking(
                db,
                provider=provider,
                model=model,
                connection_id=connection_id,
                endpoint="/v1/chat/completions",
                prompt_tokens=usage.get(
                    "prompt_tokens", 0
                ),
                completion_tokens=usage.get(
                    "completion_tokens", 0
                ),
                tokens_json=usage,
                latency_ttft=int(
                    (time.time() - (request_start_time or 0))
                    * 1000
                ),
                latency_total=int(
                    (time.time() - (request_start_time or 0))
                    * 1000
                ),
                request_body=request_body or body,
                provider_request_body=body,
                provider_response_body=usage,
                response_body=usage,
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


# ─────────────────────────────────────────────────────────────────────
# Responses-API-format upstream helpers (Grok CLI / Grok Build)
# ─────────────────────────────────────────────────────────────────────


async def _non_stream_grok_responses(
    target,
    body: dict,
    request_id: str,
    raw_body: bytes | None = None,
    db=None,
    proxy: str | None = None,
) -> tuple[JSONResponse, dict]:
    """Non-streaming call to FORMAT=openai-responses upstream.

    The upstream forces streaming (stream=true), so the SSE is consumed
    internally and the response.completed object is converted to a
    single Chat Completions JSON response.
    """
    from app.providers.grok_cli.transform import (
        responses_to_openai_response,
    )

    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    completed_response: dict = {}
    async with create_upstream_client(proxy=proxy, timeout=300.0) as client:
        async with client.stream(
            "POST", target.url, **send_kwargs,
        ) as resp:
            if resp.status_code >= 400:
                await resp.aread()
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp,
                    response=resp,
                )
            # PS hook: snapshot upstream rate-limit headers
            await observe_upstream_response(
                db, target.provider,
                target.connection_id, resp.headers,
            )
            buffer = b""
            async for chunk in resp.aiter_bytes():
                buffer += chunk
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode("utf-8", errors="ignore")
                    data_str = line.strip()
                    if not data_str.startswith("data:"):
                        continue
                    payload = data_str[5:].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict) and (
                        event.get("type") == "response.completed"
                    ):
                        completed_response = event.get("response") or {}

    if completed_response:
        translated = responses_to_openai_response(
            completed_response, body.get("model", ""),
        )
    else:
        translated = {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", ""),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    return JSONResponse(
        status_code=200,
        content=translated,
        headers={"X-Request-Id": request_id},
    ), translated


async def _stream_grok_responses(
    target,
    body: dict,
    request_id: str,
    db=None,
    provider: str = "",
    model: str = "",
    connection_id: str | None = None,
    request_body: dict | None = None,
    request_start_time: float | None = None,
    raw_body: bytes | None = None,
    active_request_id: str | None = None,
    proxy: str | None = None,
) -> StreamingResponse:
    """Streaming call to FORMAT=openai-responses upstream.

    The upstream request is opened before the StreamingResponse is
    returned, so pre-stream errors (429 quota exhausted, 401, ...)
    raise into the caller's fallback loop instead of delivering an
    empty SSE stream to the client. Translates Responses API SSE ->
    OpenAI Chat Completions SSE via ResponsesUpstreamTranslator.
    """
    from app.providers.grok_cli.stream import ResponsesUpstreamTranslator

    translator = ResponsesUpstreamTranslator(
        model=body.get("model", ""),
        request_id=f"chatcmpl-{request_id}",
    )
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    client = create_upstream_client(proxy=proxy, timeout=300.0)
    upstream_req = client.build_request(
        "POST", target.url, **send_kwargs,
    )
    resp = await client.send(upstream_req, stream=True)
    if resp.status_code >= 400:
        err_text = (await resp.aread()).decode(
            "utf-8", errors="ignore",
        )
        await resp.aclose()
        await client.aclose()
        raise httpx.HTTPStatusError(
            f"HTTP {resp.status_code}: {err_text[:300]}",
            request=upstream_req,
            response=resp,
        )
    # PS hook: snapshot upstream rate-limit headers
    await observe_upstream_response(
        db, target.provider, target.connection_id, resp.headers,
    )

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}
        try:
            buffer = b""
            async for chunk in resp.aiter_bytes():
                buffer += chunk
                while b"\n" in buffer:
                    line_bytes, buffer = buffer.split(b"\n", 1)
                    line = line_bytes.decode(
                        "utf-8", errors="ignore",
                    )
                    for ev in translator.feed(line):
                        yield ev.encode()
                        try:
                            if ev.startswith("data: {"):
                                parsed = json.loads(
                                    ev[6:].strip(),
                                )
                                if parsed.get("usage"):
                                    usage = parsed["usage"]
                        except (json.JSONDecodeError, ValueError):
                            pass
            if buffer:
                line = buffer.decode("utf-8", errors="ignore")
                for ev in translator.feed(line):
                    yield ev.encode()
        finally:
            await resp.aclose()
            await client.aclose()

        # Always finalize: upstream may close without response.completed
        for ev in translator.close():
            yield ev.encode()
            try:
                if ev.startswith("data: {"):
                    parsed = json.loads(ev[6:].strip())
                    if parsed.get("usage"):
                        usage = parsed["usage"]
            except (json.JSONDecodeError, ValueError):
                pass

        if db and provider and model:
            from app.services.usage_tracking import (
                save_request_tracking,
            )
            await save_request_tracking(
                db,
                provider=provider,
                model=model,
                connection_id=connection_id,
                endpoint="/v1/chat/completions",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                tokens_json=usage,
                latency_ttft=int(
                    (time.time() - (request_start_time or 0)) * 1000
                ),
                latency_total=int(
                    (time.time() - (request_start_time or 0)) * 1000
                ),
                request_body=request_body or body,
                provider_request_body=body,
                provider_response_body=usage,
                response_body=usage,
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
