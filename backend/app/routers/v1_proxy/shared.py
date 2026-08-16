"""Shared utilities for v1 proxy endpoints."""

import asyncio
import json
import time

import httpx
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider import ProviderConnection
from app.services.proxy import (
    calculate_cooldown,
    mark_connection_unavailable,
    should_fallback_on_error,
)
from app.services.quota import observe_upstream_response
from app.services.usage_tracking import save_request_tracking
from app.services.active_requests import track_request_end
from app.services.outbound_proxy import create_upstream_client

# ─────────────────────────────────────────────────────────────────────────────
# Shared helper classes / types
# ─────────────────────────────────────────────────────────────────────────────


class ProxyTarget:
    """Resolved upstream target returned by resolve_model_to_targets().

    Attributes:
        url: Full upstream endpoint URL.
        headers: HTTP headers for the upstream request (auth, etc.).
        model: Model name as the upstream expects it.
        provider: Canonical provider ID (e.g. "openai", "anthropic").
        connection_id: Database connection ID (string) or None.
    """

    url: str
    headers: dict[str, str]
    model: str
    provider: str
    connection_id: str | None


# ─────────────────────────────────────────────────────────────────────────────
# Fallback helper
# ─────────────────────────────────────────────────────────────────────────────


def _should_fallback_on_error(status_code: int, detail: str) -> bool:
    """Check if we should fallback to next connection on error."""
    return should_fallback_on_error(status_code, detail)


# ─────────────────────────────────────────────────────────────────────────────
# Error cooldown from inside streaming generators (uses new DB session)
# ─────────────────────────────────────────────────────────────────────────────


async def _mark_upstream_stream_error(
    provider: str | None,
    connection_id: str | None,
    model: str | None,
    status_code: int,
    error_detail: str,
) -> None:
    """Cooldown a connection from inside a streaming generator.

    Uses a fresh DB session because the request-scoped session may already
    be closed by the time the client consumes the stream.
    """
    if not connection_id:
        return
    try:
        from app.database import async_session

        async with async_session() as err_db:
            cooldown_ms, new_level = calculate_cooldown(status_code, error_detail)
            await mark_connection_unavailable(
                err_db, connection_id, cooldown_ms, model, new_level,
                status_code=status_code, error_detail=error_detail[:500],
            )
    except Exception:
        # Silently ignore — logging happens in DB layer anyway
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Provider-specific request builder (generic dispatch)
# ─────────────────────────────────────────────────────────────────────────────


async def _maybe_refresh_on_auth_error(
    target: ProxyTarget,
    db: AsyncSession,
    status_code: int | None = None,
) -> bool:
    """Ask the provider handler to refresh after an auth failure.

    When status_code is set, only 401/403 trigger a refresh attempt.
    When status_code is None (e.g. request-build failure), the handler
    decides whether refresh applies.
    """
    if not target.connection_id:
        return False
    if status_code is not None and status_code not in (401, 403):
        return False
    try:
        from app.providers.provider import Provider

        handler = Provider(target.provider).handler()
        return await handler.try_refresh_on_auth_error(
            db, target.connection_id,
        )
    except (ValueError, ModuleNotFoundError, Exception):
        return False


async def _mark_conn_failed(
    db: AsyncSession,
    connection_id: str | None,
    status_code: int,
    detail: str,
    model: str | None,
    exclude_ids: set[str],
) -> None:
    """Read backoff, apply cooldown, and exclude connection from retry."""
    if not connection_id:
        return
    conn_row = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.id == connection_id
        )
    )
    conn_obj = conn_row.scalar_one_or_none()
    current_backoff: int = 0
    if conn_obj and conn_obj.data:
        current_backoff = json.loads(conn_obj.data).get(
            "backoffLevel", 0
        )
    cooldown_ms, new_level = calculate_cooldown(
        status_code, detail, backoff_level=current_backoff,
    )
    await mark_connection_unavailable(
        db, connection_id, cooldown_ms, model, new_level,
        status_code=status_code,
        error_detail=detail,
    )
    exclude_ids.add(connection_id)


async def _build_provider_request(
    target: ProxyTarget, body: dict, conn_data: dict,
) -> tuple[bytes | None, dict[str, str] | None]:
    """Build provider-specific request body if handler supports it.

    Dispatches to handler.build_request_body() for providers that need
    custom request encoding (e.g. Qoder's WAF-bypass + COSY signing).

    Returns:
        (raw_body_bytes, signed_headers) for providers with custom encoding,
        (None, None) for standard providers that use JSON body.

    Raises:
        Exception from handler.build_request_body() so callers can refresh
        tokens or exclude the connection. Only Provider lookup failures are
        swallowed.
    """
    try:
        from app.providers.provider import Provider
        handler = Provider(target.provider).handler()
    except (ValueError, ModuleNotFoundError):
        return None, None
    if hasattr(handler, "build_request_body"):
        return await handler.build_request_body(
            target.model, body, conn_data,
        )
    return None, None


async def _before_user_forward(
    target: ProxyTarget,
    conn_data: dict | None,
    proxy: str | None,
) -> bool:
    """Provider hook before forwarding a user chat.

    False means skip this connection (try the next candidate).
    """
    try:
        from app.providers.provider import Provider
        handler = Provider(target.provider).handler()
    except (ValueError, ModuleNotFoundError):
        return True
    hook = getattr(handler, "before_user_forward", None)
    if hook is None:
        return True
    return await hook(
        url=target.url,
        model=target.model,
        conn_data=conn_data or {},
        proxy=proxy,
        connection_id=target.connection_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Qoder SSE unwrapper
# ─────────────────────────────────────────────────────────────────────────────


def _unwrap_qoder_sse_line(line: str) -> str | None:
    """Unwrap a single Qoder SSE line to OpenAI format.

    Delegates to providers/qoder/transform (PS rule).
    """
    from app.providers.qoder.transform import unwrap_qoder_sse_line

    return unwrap_qoder_sse_line(line)


def _capture_qoder_usage(line: str, current: dict) -> dict:
    """Extract the usage object from an unwrapped Qoder SSE line.

    Returns *current* unchanged when the line carries no usage data.
    """
    if not line.startswith("data: ") or line.strip() == "data: [DONE]":
        return current
    try:
        data = json.loads(line[6:])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return current
    if isinstance(data, dict) and data.get("usage"):
        return data["usage"]
    return current


# ─────────────────────────────────────────────────────────────────────────────
# Generic stream / non-stream helpers (used by chat + messages + responses)
# ─────────────────────────────────────────────────────────────────────────────


# Long-context SSE: generous write (large bodies), idle read cap,
# and no keepalive reuse (burned chunked connections).
_STREAM_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=120.0,
    write=180.0,
    pool=30.0,
)
_STREAM_LIMITS = httpx.Limits(
    max_keepalive_connections=0,
    max_connections=50,
)
_QODER_FIRST_EVENT_SECS = 60.0


def _format_proxy_stream_error(
    exc: BaseException,
    *,
    chunk_count: int = 0,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Build a non-empty Proxy error message for SSE clients (e.g. Hermes).

    httpx TimeoutException / some protocol errors often have empty ``str(e)``,
    which Hermes surfaces as the opaque ``Proxy error:`` after retries.
    """
    detail = str(exc).strip() or repr(exc)
    bits = [f"Proxy error: {type(exc).__name__}: {detail}"]
    if provider or model:
        bits.append(
            f"upstream={provider or '?'}/{model or '?'} "
            f"chunks={chunk_count}"
        )
    return " | ".join(bits)


def _http_status_error(
    status_code: int,
    detail: str,
    request: httpx.Request | None = None,
) -> httpx.HTTPStatusError:
    """Build HTTPStatusError with a synthetic response for fallback."""
    req = request or httpx.Request("POST", "https://invalid.local")
    resp = httpx.Response(status_code, text=detail, request=req)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}: {detail}",
        request=req,
        response=resp,
    )


def _qoder_error_from_unwrapped(
    unwrapped: str,
) -> tuple[int, str] | None:
    """Parse ``[qoder error N: ...]`` marker from an unwrapped SSE line."""
    import re

    if not unwrapped.startswith("data: "):
        return None
    try:
        json_data = json.loads(unwrapped[6:])
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    choices = json_data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return None
    content = (choices[0].get("delta") or {}).get("content", "")
    if not isinstance(content, str):
        return None
    # Marker is often prefixed with a leading newline
    content_l = content.lstrip()
    if not content_l.startswith("[qoder error"):
        return None
    match = re.search(
        r"\[qoder error (\d+): (.+)\]",
        content_l,
    )
    if not match:
        return None
    return int(match.group(1)), match.group(2)[:500]


def _parse_qoder_line_business_error(
    line: str,
) -> tuple[int, str] | None:
    """Detect Qoder business-error envelope on one SSE/raw line."""
    from app.providers.qoder.transform import (
        qoder_envelope_http_error,
    )

    stripped = line.strip()
    if not stripped:
        return None
    payload = stripped
    if payload.startswith("data:"):
        payload = payload[5:].strip()
    try:
        env = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(env, dict):
        return None
    direct = qoder_envelope_http_error(env)
    if direct is not None:
        return direct
    # Business error nested in statusCodeValue/headers body
    inner = env.get("body")
    if isinstance(inner, str) and inner and inner != "[DONE]":
        try:
            inner_obj = json.loads(inner)
        except json.JSONDecodeError:
            return None
        if isinstance(inner_obj, dict):
            return qoder_envelope_http_error(inner_obj)
    return None


async def _stream_response(
    target: ProxyTarget,
    body: dict,
    request_id: str,
    *,
    db: AsyncSession | None = None,
    provider: str | None = None,
    model: str | None = None,
    connection_id: str | None = None,
    request_body: dict | None = None,
    request_start_time: float | None = None,
    raw_body: bytes | None = None,
    active_request_id: str | None = None,
    proxy: str | None = None,
) -> StreamingResponse:
    """Forward request to upstream and stream SSE back to client.

    Pre-checks the upstream status; raises httpx.HTTPStatusError on 4xx/5xx
    so the caller can fallback to the next connection.

    When tracking params are provided (db, provider, etc.), saves usage and
    request detail inside the generator AFTER the stream is consumed — this is
    the only reliable way to capture usage from streaming responses.

    When *raw_body* is provided (bytes), it is sent as-is instead of JSON-
    encoding *body*.  This is required for Qoder's WAF-bypass encoding.
    """
    # Call provider's prepare_request hook (e.g. mimo-free JWT bootstrap)
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        target.headers, body = await handler.prepare_request(
            target.headers, body, stream=True,
        )
    except (ValueError, ModuleNotFoundError):
        pass

    # Determine send mode: raw bytes (Qoder) vs JSON (everything else)
    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    is_qoder = provider == "qoder"

    # Pre-flight: send a non-streaming request to check status.
    # Skip for Qoder — their endpoint returns SSE (streaming), so a pre-flight
    # would consume the entire stream. Errors are caught during streaming instead.
    if not is_qoder:
        async with create_upstream_client(proxy=proxy, timeout=30.0) as client:
            check_resp = await client.post(target.url, **send_kwargs)
            if check_resp.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"HTTP {check_resp.status_code}",
                    request=check_resp,
                    response=check_resp,
                )

    # Qoder peek: read first SSE event on the SAME signed request so
    # quota/auth envelopes (code 112, etc.) raise here for chat.py
    # fallback — instead of a 60s+ IncompleteRead mid-stream.
    qoder_prime: dict = {
        "client": None,
        "response": None,
        "buf": b"",
        "lines": [],
        "request": None,
        "byte_iter": None,
    }
    if is_qoder:
        peek_client = create_upstream_client(
            proxy=proxy,
            timeout=_STREAM_TIMEOUT,
            limits=_STREAM_LIMITS,
        )
        peek_req = peek_client.build_request(
            "POST", target.url, **send_kwargs,
        )
        try:
            peek_resp = await peek_client.send(peek_req, stream=True)
        except Exception:
            await peek_client.aclose()
            raise

        buf = b""
        primed: list[str] = []
        # ONE aiter for peek + continue (calling aiter_bytes twice
        # raises StreamConsumed).
        byte_iter = peek_resp.aiter_bytes().__aiter__()
        try:
            await observe_upstream_response(
                db, provider, connection_id, peek_resp.headers,
                model=model,
            )
            if peek_resp.status_code >= 400:
                body_preview = (await peek_resp.aread())[:500]
                detail = body_preview.decode(
                    "utf-8", errors="ignore",
                )
                raise _http_status_error(
                    peek_resp.status_code, detail, peek_req,
                )

            deadline = time.monotonic() + _QODER_FIRST_EVENT_SECS
            stream_ended = False

            def _ingest_line(line: str) -> bool:
                """Return True when a non-error content line is primed."""
                if not line.strip():
                    return False
                biz = _parse_qoder_line_business_error(line)
                if biz is not None:
                    st, detail = biz
                    raise _http_status_error(st, detail, peek_req)
                unwrapped = _unwrap_qoder_sse_line(line)
                if not unwrapped:
                    return False
                marked = _qoder_error_from_unwrapped(unwrapped)
                if marked is not None:
                    st, detail = marked
                    raise _http_status_error(st, detail, peek_req)
                primed.append(unwrapped)
                return True

            while not primed and not stream_ended:
                if time.monotonic() > deadline:
                    raise httpx.TimeoutException(
                        "Qoder first-event timeout "
                        f"({int(_QODER_FIRST_EVENT_SECS)}s)"
                    )
                try:
                    chunk = await byte_iter.__anext__()
                except StopAsyncIteration:
                    stream_ended = True
                    break
                buf += chunk
                while b"\n" in buf:
                    line_b, buf = buf.split(b"\n", 1)
                    line = line_b.decode("utf-8", errors="ignore")
                    if _ingest_line(line):
                        break

            if not primed and buf.strip():
                _ingest_line(buf.decode("utf-8", errors="ignore"))
                buf = b""

            if not primed:
                raise _http_status_error(
                    503,
                    "Qoder closed stream before first "
                    "SSE event (incomplete/empty)",
                    peek_req,
                )
        except (
            httpx.HTTPStatusError,
            httpx.TimeoutException,
        ):
            await peek_resp.aclose()
            await peek_client.aclose()
            raise
        except (
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.StreamError,
        ) as exc:
            if buf.strip():
                try:
                    line = buf.decode("utf-8", errors="ignore")
                    biz = _parse_qoder_line_business_error(line)
                    if biz is not None:
                        await peek_resp.aclose()
                        await peek_client.aclose()
                        st, detail = biz
                        raise _http_status_error(
                            st, detail, peek_req,
                        ) from exc
                    unwrapped = _unwrap_qoder_sse_line(line)
                    marked = (
                        _qoder_error_from_unwrapped(unwrapped)
                        if unwrapped else None
                    )
                    if marked is not None:
                        await peek_resp.aclose()
                        await peek_client.aclose()
                        st, detail = marked
                        raise _http_status_error(
                            st, detail, peek_req,
                        ) from exc
                except httpx.HTTPStatusError:
                    raise
            await peek_resp.aclose()
            await peek_client.aclose()
            raise _http_status_error(
                503,
                "Qoder protocol error before first SSE "
                f"event: {type(exc).__name__}: "
                f"{str(exc).strip() or repr(exc)}",
                peek_req,
            ) from exc
        except Exception:
            await peek_resp.aclose()
            await peek_client.aclose()
            raise

        qoder_prime = {
            "client": peek_client,
            "response": peek_resp,
            "buf": buf,
            "lines": primed,
            "request": peek_req,
            "byte_iter": byte_iter,
        }

    async def generate():  # type: ignore[no-untyped-def]
        usage: dict = {}
        chunk_count: int = 0
        end_status = "ok"
        # Lightweight stall sniffer (G1): summarize finish_reason / tools.
        sniff: dict = {
            "provider": provider,
            "model": model,
            "finish_reasons": [],
            "tool_delta_count": 0,
            "content_chars": 0,
            "reasoning_chars": 0,
            "max_tokens": (body or {}).get("max_tokens")
            or (body or {}).get("max_completion_tokens"),
            "tool_choice": (body or {}).get("tool_choice"),
            "n_tools": len((body or {}).get("tools") or []),
            "stream_id": None,
        }

        def _sniff_openai_sse_line(line: str) -> None:
            if not line.startswith("data: ") or line.strip() == "data: [DONE]":
                return
            try:
                data = json.loads(line[6:])
            except (json.JSONDecodeError, UnicodeDecodeError):
                return
            if not isinstance(data, dict):
                return
            if data.get("id") and not sniff["stream_id"]:
                sniff["stream_id"] = data.get("id")
            for choice in data.get("choices") or []:
                if not isinstance(choice, dict):
                    continue
                fr = choice.get("finish_reason")
                if fr:
                    sniff["finish_reasons"].append(fr)
                delta = choice.get("delta") or {}
                if not isinstance(delta, dict):
                    continue
                if delta.get("tool_calls"):
                    sniff["tool_delta_count"] += 1
                c = delta.get("content")
                if isinstance(c, str):
                    sniff["content_chars"] += len(c)
                rc = delta.get("reasoning_content")
                if isinstance(rc, str):
                    sniff["reasoning_chars"] += len(rc)

        def _flush_sniff(extra: dict | None = None) -> None:
            try:
                from pathlib import Path
                out_dir = Path(__file__).resolve().parents[3] / (
                    "tests/_stream_sniff"
                )
                out_dir.mkdir(parents=True, exist_ok=True)
                row = {
                    **sniff,
                    "ts": time.time(),
                    "chunk_count": chunk_count,
                    **(extra or {}),
                }
                with (out_dir / "streams.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except Exception as e:
                print(f"[STREAM SNIFF ERROR] {e}", flush=True)

        async def _consume_qoder_resp(
            resp: httpx.Response,
            initial_buf: bytes,
            primed_lines: list[str],
            byte_iter=None,
        ):
            nonlocal chunk_count, usage
            for unwrapped in primed_lines:
                chunk_count += 1
                marked = _qoder_error_from_unwrapped(unwrapped)
                if marked is not None:
                    st, detail = marked
                    await _mark_upstream_stream_error(
                        provider, connection_id, model, st, detail,
                    )
                    raise _http_status_error(
                        st, detail, resp.request,
                    )
                _sniff_openai_sse_line(unwrapped)
                yield f"{unwrapped}\n\n".encode()
                usage = _capture_qoder_usage(unwrapped, usage)
            qoder_buf = initial_buf
            # Continue the SAME aiter from peek when provided.
            if byte_iter is None:
                byte_iter = resp.aiter_bytes().__aiter__()
            while True:
                try:
                    chunk = await byte_iter.__anext__()
                except StopAsyncIteration:
                    break
                chunk_count += 1
                qoder_buf += chunk
                while b"\n" in qoder_buf:
                    line_b, qoder_buf = qoder_buf.split(b"\n", 1)
                    line = line_b.decode("utf-8", errors="ignore")
                    biz = _parse_qoder_line_business_error(line)
                    if biz is not None:
                        st, detail = biz
                        await _mark_upstream_stream_error(
                            provider, connection_id, model,
                            st, detail,
                        )
                        raise _http_status_error(
                            st, detail, resp.request,
                        )
                    unwrapped = _unwrap_qoder_sse_line(line)
                    if not unwrapped:
                        continue
                    if unwrapped.strip() == "data: [DONE]":
                        continue
                    marked = _qoder_error_from_unwrapped(unwrapped)
                    if marked is not None:
                        st, detail = marked
                        await _mark_upstream_stream_error(
                            provider, connection_id, model,
                            st, detail,
                        )
                        raise _http_status_error(
                            st, detail, resp.request,
                        )
                    _sniff_openai_sse_line(unwrapped)
                    yield f"{unwrapped}\n\n".encode()
                    usage = _capture_qoder_usage(unwrapped, usage)
            if qoder_buf.strip():
                line = qoder_buf.decode("utf-8", errors="ignore")
                biz = _parse_qoder_line_business_error(line)
                if biz is not None:
                    st, detail = biz
                    await _mark_upstream_stream_error(
                        provider, connection_id, model, st, detail,
                    )
                    raise _http_status_error(
                        st, detail, resp.request,
                    )
                unwrapped = _unwrap_qoder_sse_line(line)
                if unwrapped:
                    marked = _qoder_error_from_unwrapped(unwrapped)
                    if marked is not None:
                        st, detail = marked
                        await _mark_upstream_stream_error(
                            provider, connection_id, model,
                            st, detail,
                        )
                        raise _http_status_error(
                            st, detail, resp.request,
                        )
                    _sniff_openai_sse_line(unwrapped)
                    yield f"{unwrapped}\n\n".encode()
                    usage = _capture_qoder_usage(unwrapped, usage)

        try:
            if is_qoder and qoder_prime.get("response") is not None:
                peek_client = qoder_prime["client"]
                peek_resp = qoder_prime["response"]
                try:
                    try:
                        async for item in _consume_qoder_resp(
                            peek_resp,
                            qoder_prime.get("buf") or b"",
                            list(qoder_prime.get("lines") or []),
                            byte_iter=qoder_prime.get("byte_iter"),
                        ):
                            yield item
                    except asyncio.CancelledError:
                        end_status = "error"
                        _flush_sniff({"ended": "cancelled"})
                        raise
                    except GeneratorExit:
                        end_status = "error"
                        _flush_sniff({"ended": "client_disconnect"})
                        raise
                    except Exception as e:
                        end_status = "error"
                        # No same-body reconnect: Qoder returns code 103
                        # "Duplicate request" for resent COSY payloads.
                        err_msg = _format_proxy_stream_error(
                            e,
                            chunk_count=chunk_count,
                            provider=provider,
                            model=model,
                        )
                        if isinstance(e, httpx.HTTPStatusError):
                            err_msg = (
                                f"Proxy error: HTTP "
                                f"{e.response.status_code}: "
                                f"{(e.response.text or '')[:400]}"
                                f" | upstream={provider}/{model} "
                                f"chunks={chunk_count}"
                            )
                            try:
                                await _mark_upstream_stream_error(
                                    provider,
                                    connection_id,
                                    model,
                                    e.response.status_code,
                                    (e.response.text or "")[:500],
                                )
                            except Exception:
                                pass
                        _flush_sniff({
                            "ended": "error",
                            "error": err_msg[:300],
                        })
                        print(
                            f"[STREAM PROXY ERROR] {err_msg}",
                            flush=True,
                        )
                        error_data = json.dumps({
                            "error": {
                                "message": err_msg,
                                "type": "proxy_error",
                            }
                        })
                        yield f"data: {error_data}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                    else:
                        _flush_sniff({"ended": "ok"})
                        yield b"data: [DONE]\n\n"
                finally:
                    try:
                        await peek_resp.aclose()
                    except Exception:
                        pass
                    try:
                        await peek_client.aclose()
                    except Exception:
                        pass
            else:
                async with create_upstream_client(
                    proxy=proxy,
                    timeout=_STREAM_TIMEOUT,
                    limits=_STREAM_LIMITS,
                ) as client:
                    try:
                        async with client.stream(
                            "POST",
                            target.url,
                            **send_kwargs,
                        ) as resp:
                            await observe_upstream_response(
                                db, provider, connection_id,
                                resp.headers,
                                model=model,
                            )
                            if resp.status_code >= 400:
                                body_preview = (
                                    await resp.aread()
                                )[:500]
                                raise httpx.HTTPStatusError(
                                    f"HTTP {resp.status_code}: "
                                    f"{body_preview.decode('utf-8', errors='ignore')}",
                                    request=resp.request,
                                    response=resp,
                                )
                            async for chunk in resp.aiter_bytes():
                                chunk_count += 1
                                yield chunk
                                try:
                                    text = chunk.decode(
                                        "utf-8", errors="ignore",
                                    )
                                    for line in text.split("\n"):
                                        _sniff_openai_sse_line(line)
                                        if (
                                            line.startswith("data: ")
                                            and line.strip()
                                            != "data: [DONE]"
                                        ):
                                            data = json.loads(line[6:])
                                            if (
                                                "usage" in data
                                                and data["usage"]
                                            ):
                                                usage = data["usage"]
                                except (
                                    json.JSONDecodeError,
                                    UnicodeDecodeError,
                                ):
                                    pass
                    except asyncio.CancelledError:
                        end_status = "error"
                        _flush_sniff({"ended": "cancelled"})
                        raise
                    except GeneratorExit:
                        end_status = "error"
                        _flush_sniff({"ended": "client_disconnect"})
                        raise
                    except Exception as e:
                        end_status = "error"
                        err_msg = _format_proxy_stream_error(
                            e,
                            chunk_count=chunk_count,
                            provider=provider,
                            model=model,
                        )
                        _flush_sniff({
                            "ended": "error",
                            "error": err_msg[:300],
                        })
                        print(
                            f"[STREAM PROXY ERROR] {err_msg}",
                            flush=True,
                        )
                        error_data = json.dumps({
                            "error": {
                                "message": err_msg,
                                "type": "proxy_error",
                            }
                        })
                        yield f"data: {error_data}\n\n".encode()
                        yield b"data: [DONE]\n\n"
                    else:
                        _flush_sniff({"ended": "ok"})
                        yield b"data: [DONE]\n\n"

            # Save usage tracking AFTER stream is consumed
            if (
                not usage.get("prompt_tokens")
                and not usage.get("completion_tokens")
            ):
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": chunk_count * 10,
                    "total_tokens": chunk_count * 10,
                    "_estimated": True,
                }

            if db and provider and request_start_time:
                try:
                    from app.database import async_session
                    async with async_session() as tracking_db:
                        total_latency_ms = int(
                            (time.time() - request_start_time) * 1000
                        )
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get(
                            "completion_tokens", 0,
                        )
                        await save_request_tracking(
                            tracking_db,
                            provider=provider,
                            model=model,
                            connection_id=connection_id,
                            endpoint="/v1/chat/completions",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
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
                    print(f"[STREAM TRACKING ERROR] {e}", flush=True)
        finally:
            # Always clear active tracking — client disconnect /
            # CancelledError previously skipped track_request_end and
            # left /usage animations stuck until process restart.
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


async def _non_stream_response(
    target: ProxyTarget, body: dict, request_id: str,
    *,
    raw_body: bytes | None = None,
    proxy: str | None = None,
    db=None,
) -> tuple[JSONResponse, dict]:
    """Forward request to upstream and return complete response.

    Returns (JSONResponse, raw_data_dict) so callers can extract usage info.
    """
    # Call provider's prepare_request hook (e.g. mimo-free JWT bootstrap)
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        target.headers, body = await handler.prepare_request(
            target.headers, body, stream=False,
        )
    except (ValueError, ModuleNotFoundError):
        pass

    send_kwargs: dict = {"headers": target.headers}
    if raw_body is not None:
        send_kwargs["content"] = raw_body
    else:
        send_kwargs["json"] = body

    async with create_upstream_client(proxy=proxy, timeout=300.0) as client:
        resp = await client.post(target.url, **send_kwargs)
        if db is not None:
            await observe_upstream_response(
                db, target.provider, target.connection_id,
                resp.headers, model=target.model,
            )
        resp.raise_for_status()

        # Unwrap provider-specific response envelope
        try:
            from app.providers.provider import Provider
            p = Provider(target.provider)
            handler = p.handler()
            data = handler.unwrap_response(resp.text)
        except Exception:
            # Fallback: standard JSON parse
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text[:2000]}

        response = JSONResponse(
            status_code=resp.status_code,
            content=data,
            headers={"X-Request-Id": request_id},
        )
        return response, data


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings helpers
# ─────────────────────────────────────────────────────────────────────────────


def _build_embeddings_url(target: ProxyTarget) -> str:
    """Derive the embeddings endpoint URL using handler."""
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        return handler.build_embeddings_url(target.url)
    except (ValueError, ModuleNotFoundError):
        # Fallback: standard OpenAI-compat
        if target.url.endswith("/chat/completions"):
            return target.url[:-len("/chat/completions")] + "/embeddings"
        return target.url.rstrip("/") + "/embeddings"


def _build_embeddings_body(target: ProxyTarget, body: dict) -> dict:
    """Transform the embeddings request body using handler."""
    try:
        from app.providers.provider import Provider
        p = Provider(target.provider)
        handler = p.handler()
        return handler.build_embeddings_body(target.model, body)
    except (ValueError, ModuleNotFoundError):
        # Fallback: standard OpenAI-compat
        return {**body, "model": target.model}


# ─────────────────────────────────────────────────────────────────────────────
# Default model list helper
# ─────────────────────────────────────────────────────────────────────────────


def _get_default_models(provider: str) -> list[str]:
    """Return default model list for a provider."""
    defaults: dict[str, list[str]] = {
        "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o1-mini"],
        "anthropic": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "openrouter": ["openai/gpt-4o", "anthropic/claude-sonnet-4-20250514", "meta-llama/llama-3.1-70b-instruct"],
        "deepseek": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "google": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
        "groq": ["llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "together": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo", "mistralai/Mixtral-8x7B-Instruct-v0.1"],
        "mistral": ["mistral-large-latest", "mistral-small-latest", "codestral-latest"],
        "xai": ["grok-beta", "grok-2"],
        "qwen": ["qwen-turbo", "qwen-plus", "qwen-max"],
    }
    return defaults.get(provider, ["default"])
