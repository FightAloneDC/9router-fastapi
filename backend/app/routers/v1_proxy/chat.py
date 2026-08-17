"""POST /v1/chat/completions — OpenAI-compatible chat completions proxy."""

import asyncio
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
    MAX_FALLBACK_ATTEMPTS,
    _stream_response,
    _non_stream_response,
    _should_fallback_on_error,
    _rewrite_body_after_error,
    _build_provider_request,
    _before_user_forward,
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
    body_retry_ids: set[str] = set()
    last_error_detail: str | None = None
    last_error_status: int = 503

    while True:
        if len(exclude_ids) >= MAX_FALLBACK_ATTEMPTS:
            break
        if await request.is_disconnected():
            return JSONResponse(
                status_code=499,
                content={
                    "error": {
                        "message": "Client disconnected",
                    },
                },
            )

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
                    last_error_detail = str(exc)
                    last_error_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    exclude_ids.add(target.connection_id)
                    continue
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
                if not await _before_user_forward(
                    target, conn_data, proxy,
                ):
                    last_error_detail = (
                        "quality-gate: probe did not return 407"
                    )
                    last_error_status = 503
                    exclude_ids.add(target.connection_id)
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
                        request_body=body,
                    )
                else:
                    resp, resp_data = await _non_stream_response(
                        target, forward_body, request_id,
                        raw_body=raw_body,
                        proxy=proxy,
                        db=db,
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

            # PS: same-connection body rewrite (e.g. strip reasoning)
            if conn_id and conn_id not in body_retry_ids:
                rewritten = _rewrite_body_after_error(
                    target.provider,
                    e.response.status_code,
                    e.response.text,
                    target.model,
                    body,
                )
                if rewritten is not None:
                    body_retry_ids.add(conn_id)
                    body = rewritten
                    continue

            if not _should_fallback_on_error(
                e.response.status_code,
                e.response.text,
                target.provider,
            ):
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

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            track_request_end(active_request_id, status="error")
            last_error_detail = str(e)
            last_error_status = 503
            await _mark_conn_failed(
                db, target.connection_id, 503,
                last_error_detail, model, exclude_ids,
            )
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
        end_status = "ok"
        try:
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
                    end_status = "error"
                    raise
                except Exception:
                    end_status = "error"
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
        except (asyncio.CancelledError, GeneratorExit):
            end_status = "error"
            raise
        finally:
            if active_request_id:
                track_request_end(
                    active_request_id, status=end_status,
                )

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


def _usage_from_sse(event: str, usage: dict) -> dict:
    try:
        if event.startswith("data: {"):
            parsed = json.loads(event[6:].strip())
            if parsed.get("usage"):
                return parsed["usage"]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return usage


async def _translate_grok_upstream(
    resp,
    translator,
    assembler,
) -> tuple[list[str], dict]:
    """Consume Responses SSE and return Chat Completions SSE strings."""
    events: list[str] = []
    usage: dict = {}
    buffer = b""
    async for chunk in resp.aiter_bytes():
        buffer += chunk
        while b"\n" in buffer:
            line_bytes, buffer = buffer.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="ignore")
            for ev in translator.feed(line):
                assembler.feed(ev)
                events.append(ev)
                usage = _usage_from_sse(ev, usage)
    if buffer:
        line = buffer.decode("utf-8", errors="ignore")
        for ev in translator.feed(line):
            assembler.feed(ev)
            events.append(ev)
            usage = _usage_from_sse(ev, usage)
    for ev in translator.close():
        assembler.feed(ev)
        events.append(ev)
        usage = _usage_from_sse(ev, usage)
    return events, usage


async def _post_phantom_retry(
    target,
    retry_json: dict,
    request_id: str,
    hop: int,
    proxy: str | None,
    db=None,
    model: str = "",
):
    """POST one inject retry. Returns (ok_tuple | None, status, error)."""
    from app.providers.grok_cli.debug_dump import (
        ChatSseAssembler,
        begin_dump,
        finish_dump,
    )
    from app.providers.grok_cli.stream import (
        ResponsesUpstreamTranslator,
    )

    cid = getattr(target, "connection_id", None)
    retry_dump = begin_dump(
        request_id=f"r{hop}-{request_id}",
        endpoint="/v1/chat/completions",
        stream=True,
        client_request={
            "_retry": True,
            "nudge": True,
            "hop": hop,
        },
        upstream_request=retry_json,
        model=model,
        connection_id=cid,
    )
    translator = ResponsesUpstreamTranslator(
        model=model,
        request_id=f"chatcmpl-{request_id}-r{hop}",
    )
    assembler = ChatSseAssembler()
    try:
        async with create_upstream_client(
            proxy=proxy, timeout=300.0,
        ) as client:
            async with client.stream(
                "POST",
                target.url,
                headers=target.headers,
                json=retry_json,
            ) as resp:
                await observe_upstream_response(
                    db, target.provider, cid, resp.headers,
                    model=target.model,
                )
                if resp.status_code >= 400:
                    err = (await resp.aread()).decode(
                        "utf-8", errors="ignore",
                    )[:800]
                    print(
                        f"[grok-cli retry] hop={hop} HTTP "
                        f"{resp.status_code}: {err}",
                        flush=True,
                    )
                    finish_dump(
                        retry_dump, None,
                        status="error",
                        error=f"HTTP {resp.status_code}: {err}",
                    )
                    return None, resp.status_code, err
                events, usage = await _translate_grok_upstream(
                    resp, translator, assembler,
                )
    except Exception as exc:
        print(
            f"[grok-cli retry] hop={hop} failed: {exc}",
            flush=True,
        )
        finish_dump(
            retry_dump, None, status="error", error=str(exc),
        )
        return None, 500, str(exc)
    finish_dump(retry_dump, assembler.to_dict(), status="ok")
    print(
        f"[grok-cli retry] hop={hop} ok tools="
        f"{assembler.to_dict().get('tool_calls')}",
        flush=True,
    )
    return (events, assembler, usage, retry_json), 200, None


async def _retry_phantom_grok_write(
    target,
    raw_body: bytes | None,
    body: dict,
    assembled: dict,
    request_id: str,
    proxy: str | None,
    db=None,
    resolve_model: str = "",
):
    """Inject-retry a phantom write; hop on exhausted / fallback errors."""
    from app.providers.grok_cli.anomaly import inject_retry_upstream
    from app.providers.grok_cli.debug_dump import parse_upstream_body
    from app.services.proxy import (
        resolve_model_to_targets,
        should_fallback_on_error,
    )
    from .shared import _mark_conn_failed

    upstream = parse_upstream_body(raw_body, body)
    if not isinstance(upstream, dict):
        print("[grok-cli retry] no upstream body", flush=True)
        return None
    retry_json = inject_retry_upstream(upstream, assembled)
    lookup = resolve_model or body.get("model") or ""
    tried: set[str] = set()
    current = target
    hop = 0
    while current is not None and hop < 8:
        hop += 1
        cid = getattr(current, "connection_id", None)
        if cid:
            tried.add(str(cid))
        ok, status, err = await _post_phantom_retry(
            current, retry_json, request_id, hop,
            proxy, db, model=lookup,
        )
        if ok:
            return ok
        if not should_fallback_on_error(status, err or ""):
            return None
        if db and cid:
            await _mark_conn_failed(
                db, cid, status, err or "",
                lookup, tried,
            )
        if not db or not lookup:
            return None
        nxt = await resolve_model_to_targets(
            db, lookup, True, exclude_ids=tried,
        )
        current = nxt[0] if nxt else None
        if current:
            print(
                f"[grok-cli retry] hop to "
                f"{current.connection_id}",
                flush=True,
            )
    return None


async def _non_stream_grok_responses(
    target,
    body: dict,
    request_id: str,
    raw_body: bytes | None = None,
    db=None,
    proxy: str | None = None,
    request_body: dict | None = None,
) -> tuple[JSONResponse, dict]:
    """Non-streaming call to FORMAT=openai-responses upstream.

    The upstream forces streaming (stream=true), so the SSE is consumed
    internally and the response.completed object is converted to a
    single Chat Completions JSON response.
    """
    from app.providers.grok_cli.debug_dump import (
        begin_dump,
        finish_dump,
        parse_upstream_body,
        response_from_chat_completion,
    )
    from app.providers.grok_cli.transform import (
        responses_to_openai_response,
    )

    dump = begin_dump(
        request_id=request_id,
        endpoint="/v1/chat/completions",
        stream=False,
        client_request=request_body or body,
        upstream_request=parse_upstream_body(raw_body, body),
        model=(request_body or body).get("model") or body.get(
            "model", "",
        ),
        connection_id=getattr(target, "connection_id", None),
    )

    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    completed_response: dict = {}
    try:
        async with create_upstream_client(
            proxy=proxy, timeout=300.0,
        ) as client:
            async with client.stream(
                "POST", target.url, **send_kwargs,
            ) as resp:
                await observe_upstream_response(
                    db, target.provider,
                    target.connection_id, resp.headers,
                    model=target.model,
                )
                if resp.status_code >= 400:
                    await resp.aread()
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp,
                        response=resp,
                    )
                buffer = b""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode(
                            "utf-8", errors="ignore",
                        )
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
                            completed_response = (
                                event.get("response") or {}
                            )

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
                    "message": {
                        "role": "assistant",
                        "content": "",
                    },
                    "finish_reason": "stop",
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        assembled = response_from_chat_completion(translated)
        finish_dump(dump, assembled, status="ok")
        from app.providers.grok_cli.anomaly import is_phantom_write
        from app.providers.grok_cli.constants import (
            PHANTOM_WRITE_RETRY,
        )
        if (
            PHANTOM_WRITE_RETRY
            and is_phantom_write(request_body or body, assembled)
        ):
            print(
                "[grok-cli retry] phantom write, retrying",
                flush=True,
            )
            retried = await _retry_phantom_grok_write(
                target, raw_body, body, assembled,
                request_id, proxy, db,
                resolve_model=(request_body or body).get("model", ""),
            )
            if retried:
                _, retry_asm, _, retry_json = retried
                assembled = retry_asm.to_dict()
                translated = {
                    "id": f"chatcmpl-{request_id}-retry",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": body.get("model", ""),
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": assembled.get("content") or None,
                            "tool_calls": (
                                assembled.get("tool_calls") or None
                            ),
                            **({
                                "reasoning_content": assembled[
                                    "reasoning_content"
                                ],
                            } if assembled.get(
                                "reasoning_content",
                            ) else {}),
                        },
                        "finish_reason": assembled.get(
                            "finish_reason",
                        ) or "stop",
                    }],
                    "usage": assembled.get("usage") or {},
                }
                if not translated["choices"][0]["message"].get(
                    "tool_calls",
                ):
                    translated["choices"][0]["message"].pop(
                        "tool_calls", None,
                    )
        return JSONResponse(
            status_code=200,
            content=translated,
            headers={"X-Request-Id": request_id},
        ), translated
    except Exception as exc:
        finish_dump(dump, None, status="error", error=str(exc))
        raise


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
    from app.providers.grok_cli.debug_dump import (
        ChatSseAssembler,
        begin_dump,
        finish_dump,
        parse_upstream_body,
    )
    from app.providers.grok_cli.stream import ResponsesUpstreamTranslator

    translator = ResponsesUpstreamTranslator(
        model=body.get("model", ""),
        request_id=f"chatcmpl-{request_id}",
    )
    assembler = ChatSseAssembler()
    dump = begin_dump(
        request_id=request_id,
        endpoint="/v1/chat/completions",
        stream=True,
        client_request=request_body or body,
        upstream_request=parse_upstream_body(raw_body, body),
        model=model or body.get("model", ""),
        connection_id=connection_id,
    )
    dump_status = ["ok"]
    dump_error: list[str | None] = [None]
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    client = create_upstream_client(proxy=proxy, timeout=300.0)
    upstream_req = client.build_request(
        "POST", target.url, **send_kwargs,
    )
    try:
        resp = await client.send(upstream_req, stream=True)
    except Exception as exc:
        await client.aclose()
        finish_dump(dump, None, status="error", error=str(exc))
        raise
    await observe_upstream_response(
        db, target.provider, target.connection_id, resp.headers,
        model=target.model,
    )
    if resp.status_code >= 400:
        err_text = (await resp.aread()).decode(
            "utf-8", errors="ignore",
        )
        await resp.aclose()
        await client.aclose()
        finish_dump(
            dump, None, status="error",
            error=f"HTTP {resp.status_code}: {err_text[:300]}",
        )
        raise httpx.HTTPStatusError(
            f"HTTP {resp.status_code}: {err_text[:300]}",
            request=upstream_req,
            response=resp,
        )

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}
        end_status = "ok"
        final_assembler = assembler
        try:
            try:
                events, usage = await _translate_grok_upstream(
                    resp, translator, assembler,
                )
            finally:
                await resp.aclose()
                await client.aclose()

            from app.providers.grok_cli.anomaly import (
                is_phantom_write,
            )
            from app.providers.grok_cli.constants import (
                PHANTOM_WRITE_RETRY,
            )
            assembled = assembler.to_dict()
            finish_dump(
                dump, assembled, status="ok",
            )
            if (
                PHANTOM_WRITE_RETRY
                and is_phantom_write(
                    request_body or body, assembled,
                )
            ):
                print(
                    "[grok-cli retry] phantom write, retrying",
                    flush=True,
                )
                retried = await _retry_phantom_grok_write(
                    target, raw_body, body, assembled,
                    request_id, proxy, db,
                    resolve_model=(
                        request_body or body
                    ).get("model", ""),
                )
                if retried:
                    events, retry_asm, retry_usage, _retry_json = (
                        retried
                    )
                    final_assembler = retry_asm
                    if retry_usage:
                        usage = retry_usage

            for ev in events:
                yield ev.encode()

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
                    completion_tokens=usage.get(
                        "completion_tokens", 0,
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
        except (asyncio.CancelledError, GeneratorExit):
            end_status = "error"
            dump_status[0] = "cancelled"
            raise
        except Exception as exc:
            end_status = "error"
            dump_status[0] = "error"
            dump_error[0] = str(exc)
            raise
        finally:
            if dump_status[0] != "ok":
                finish_dump(
                    dump,
                    final_assembler.to_dict(),
                    status=dump_status[0],
                    error=dump_error[0],
                )
            if active_request_id:
                track_request_end(
                    active_request_id, status=end_status,
                )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-Id": request_id,
        },
    )
