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


# ─────────────────────────────────────────────────────────────────────────────
# Qoder SSE unwrapper
# ─────────────────────────────────────────────────────────────────────────────


def _unwrap_qoder_sse_line(line: str) -> str | None:
    """Unwrap a single Qoder SSE line to OpenAI format.

    Qoder may send:
      - New: data: {"headers":{...},"body":"..."}
      - Old: data: {"statusCodeValue":200,"body":"..."}
      - Direct: data: {"choices":[...],...}

    Returns:
        Unwrapped line or None if should be skipped
    """
    trimmed = line.strip()
    if not trimmed or not trimmed.startswith("data:"):
        return None

    data = trimmed[5:].strip()
    if data == "[DONE]":
        return "data: [DONE]"

    try:
        envelope = json.loads(data)
    except json.JSONDecodeError:
        return None

    # New format: {"headers":{...},"body":"..."}
    if "headers" in envelope and "body" in envelope:
        inner = envelope.get("body", "")
        if not inner:
            return None
        if inner == "[DONE]":
            return "data: [DONE]"
        sanitized = inner.replace("\r\n", "").replace("\n", "")
        return f"data: {sanitized}"

    # Old format: {"statusCodeValue":200,"body":"..."}
    status = envelope.get("statusCodeValue", 200)
    inner = envelope.get("body", "")

    if status != 200:
        error_chunk = json.dumps({
            "id": f"qoder-error-{int(time.time())}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "qoder",
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n[qoder error {status}: {inner[:200]}]"},
                "finish_reason": "stop",
            }],
        })
        return f"data: {error_chunk}"

    if not inner:
        return None

    if inner == "[DONE]":
        return "data: [DONE]"

    # Sanitize inner - remove embedded newlines
    sanitized = inner.replace("\r\n", "").replace("\n", "")
    return f"data: {sanitized}"


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
                        # PS hook: snapshot upstream rate-limit headers
                        await observe_upstream_response(
                            db, provider, connection_id, resp.headers,
                        )
                        # Qoder SSE lines may be split across read boundaries;
                        # buffer bytes until a full line is available, or the
                        # fragments are dropped and deltas are lost (corrupted
                        # tool-call arguments / mangled text).
                        qoder_buf = b""
                        async for chunk in resp.aiter_bytes():
                            chunk_count += 1
                            if is_qoder:
                                # Qoder sends wrapped SSE:
                                # {"statusCodeValue":200,"body":"..."}
                                qoder_buf += chunk
                                while b"\n" in qoder_buf:
                                    line_b, qoder_buf = qoder_buf.split(
                                        b"\n", 1,
                                    )
                                    line = line_b.decode(
                                        "utf-8", errors="ignore",
                                    )
                                    unwrapped = _unwrap_qoder_sse_line(line)
                                    if unwrapped:
                                        _sniff_openai_sse_line(unwrapped)
                                        yield f"{unwrapped}\n\n".encode()
                                        usage = _capture_qoder_usage(
                                            unwrapped, usage,
                                        )
                                        # CHECK FOR QODER STREAMING ERRORS
                                        try:
                                            json_data = json.loads(
                                                unwrapped[6:],
                                            )
                                            choices = (
                                                json_data.get("choices") or []
                                            )
                                            if (
                                                choices
                                                and isinstance(choices[0], dict)
                                            ):
                                                delta = choices[0].get(
                                                    "delta", {},
                                                )
                                                content = delta.get(
                                                    "content", "",
                                                )
                                                if (
                                                    isinstance(content, str)
                                                    and content.startswith(
                                                        "[qoder error"
                                                    )
                                                ):
                                                    import re
                                                    match = re.search(
                                                        r"\[qoder error "
                                                        r"(\d+): (.+)\]",
                                                        content,
                                                    )
                                                    if match:
                                                        status_code = int(
                                                            match.group(1)
                                                        )
                                                        error_detail = (
                                                            match.group(2)[:500]
                                                        )
                                                        await (
                                                            _mark_upstream_stream_error(
                                                                provider,
                                                                connection_id,
                                                                model,
                                                                status_code,
                                                                error_detail,
                                                            )
                                                        )
                                                        raise httpx.HTTPStatusError(
                                                            f"HTTP {status_code}: "
                                                            f"{error_detail}",
                                                            request=resp.request,
                                                            response=resp,
                                                        )
                                        except (
                                            json.JSONDecodeError,
                                            IndexError,
                                            KeyError,
                                            ValueError,
                                            AttributeError,
                                        ):
                                            pass
                            else:
                                yield chunk
                                # Parse SSE to capture usage from last chunk
                                try:
                                    text = chunk.decode(
                                        "utf-8", errors="ignore",
                                    )
                                    for line in text.split("\n"):
                                        _sniff_openai_sse_line(line)
                                        if (
                                            line.startswith("data: ")
                                            and line.strip() != "data: [DONE]"
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
                        # Flush a final Qoder line without trailing newline
                        if is_qoder and qoder_buf:
                            line = qoder_buf.decode(
                                "utf-8", errors="ignore",
                            )
                            unwrapped = _unwrap_qoder_sse_line(line)
                            if unwrapped:
                                _sniff_openai_sse_line(unwrapped)
                                yield f"{unwrapped}\n\n".encode()
                                usage = _capture_qoder_usage(
                                    unwrapped, usage,
                                )
                except asyncio.CancelledError:
                    end_status = "error"
                    _flush_sniff({"ended": "cancelled"})
                    raise
                except GeneratorExit:
                    # Client disconnected mid-stream. Do not yield [DONE]:
                    # yielding during GeneratorExit raises
                    # "generator ignored GeneratorExit" and spams logs.
                    end_status = "error"
                    _flush_sniff({"ended": "client_disconnect"})
                    raise
                except Exception as e:
                    end_status = "error"
                    _flush_sniff({"ended": "error", "error": str(e)[:300]})
                    error_data = json.dumps({
                        "error": {
                            "message": f"Proxy error: {str(e)}",
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
