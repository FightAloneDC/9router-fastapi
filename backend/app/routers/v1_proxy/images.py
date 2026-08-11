"""POST /v1/images/generations — OpenAI-compatible image generation proxy."""

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
    get_connections_cached,
    get_provider_strategy,
    select_connection_for_provider,
    clear_connection_error,
    update_connection_usage,
    _resolve_provider_alias,
    _resolve_base_url,
)
from app.services.image_adapters import IMAGE_ADAPTERS, image_comfyui, _stub_adapter
from app.services.usage_tracking import save_request_tracking
from app.providers.provider import Provider
from app.routers.providers.helpers import _get_provider_config

from .shared import _should_fallback_on_error, _mark_conn_failed

router = APIRouter()

_NOAUTH_PROVIDERS: set[str] = {"sdwebui", "comfyui"}
_IMAGE_KNOWN_KEYS: set[str] = {"model", "prompt", "n", "size", "response_format", "quality", "style"}


@router.post("/images/generations")
async def images_generations(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """OpenAI-compatible image generation proxy.

    Model field encodes provider and model: ``provider/model``.

    Examples:
      - ``openai/dall-e-3``           → openai, dall-e-3
      - ``siliconflow/black-forest-labs/FLUX.1-schnell`` → siliconflow, black-forest-labs/FLUX.1-schnell

    Body fields (OpenAI spec):
      - model (required): provider/model string
      - prompt (required): text prompt
      - n: number of images (default 1)
      - size: "1024x1024" (default), "512x512", "1792x1024", etc.
      - response_format: "url" (default) or "b64_json"
      - quality: "standard" or "hd" (provider-dependent)
      - style: "vivid" or "natural" (provider-dependent)

    Response: OpenAI-compatible ``{"created": ..., "data": [...]}``
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    model_str: str | None = body.get("model")
    prompt: str | None = body.get("prompt")
    if not model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model",
        )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: prompt",
        )

    # ── 1. Parse provider from model string ──
    if "/" not in model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model must be in 'provider/model' format (e.g. 'openai/dall-e-3')",
        )

    provider_name, image_model = model_str.split("/", 1)
    provider_id: str = _resolve_provider_alias(provider_name)

    # ── 2. Resolve handler or adapter for this provider ──
    handler = None
    try:
        p = Provider(provider_id)
        handler = p.handler()
    except (ValueError, ModuleNotFoundError):
        pass

    has_handler_image = handler and hasattr(handler, "build_image_request")

    adapter = None if has_handler_image else IMAGE_ADAPTERS.get(provider_id)
    if adapter is None and not has_handler_image:
        supported = sorted(
            k for k, v in IMAGE_ADAPTERS.items()
            if v is not image_comfyui and v is not _stub_adapter
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"Image provider '{provider_id}' is not yet supported. "
                f"Supported: {', '.join(supported)}"
            ),
        )

    # ── 3. Extract optional fields ──
    n: int = body.get("n", 1)
    size: str = body.get("size", "1024x1024")
    response_format: str = body.get("response_format", "url")
    quality: str | None = body.get("quality")
    style: str | None = body.get("style")

    # Pass-through any extra body fields (provider-specific)
    extra_body: dict | None = {k: v for k, v in body.items() if k not in _IMAGE_KNOWN_KEYS} or None

    # ── 4. Lookup active connections + strategy ──
    connections = await get_connections_cached(db, provider_id)
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No active connection for provider: {provider_id}",
        )

    strategy, sticky_limit = await get_provider_strategy(db, provider_id)

    # ── 5. Fallback loop with cooldown, model lock, and strategy ──
    request_id: str = str(uuid.uuid4())
    exclude_ids: set[str] = set()
    last_error: dict | None = None

    while True:
        conn = select_connection_for_provider(
            connections=list(connections),
            provider_id=provider_id,
            strategy=strategy,
            sticky_limit=sticky_limit,
            exclude_ids=exclude_ids,
            model=image_model,
        )
        if not conn:
            break

        conn_data: dict = json.loads(conn.data) if conn.data else {}
        api_key: str = conn_data.get("apiKey") or conn_data.get("api_key") or ""
        base_url: str = conn_data.get("baseUrl") or _resolve_base_url(provider_id, conn_data)
        conn_id: str = str(conn.id)

        if not base_url and provider_id not in _NOAUTH_PROVIDERS:
            last_error = {"status": 500, "detail": f"No base_url for provider {provider_id}"}
            exclude_ids.add(conn_id)
            continue

        if not base_url and provider_id in _NOAUTH_PROVIDERS:
            if handler:
                base_url = handler.config.BASE_URL
            else:
                defaults: dict = _get_provider_config(provider_id)
                base_url = defaults.get("baseUrl", "http://localhost:7860")

        try:
            request_start_time: float = time.time()
            async with httpx.AsyncClient(timeout=120.0) as client:
                if has_handler_image and handler is not None:
                    url, method, headers, req_body = handler.build_image_request(
                        base_url=base_url,
                        model=image_model,
                        prompt=prompt,
                        n=n,
                        size=size,
                        response_format=response_format,
                        quality=quality,
                        style=style,
                        extra_body=extra_body,
                    )
                    if method == "GET":
                        resp = await client.get(url, headers=headers)
                    else:
                        resp = await client.post(url, headers=headers, json=req_body)
                    resp.raise_for_status()
                    images = handler.parse_image_response(resp.json())
                else:
                    images = await adapter(
                        client,
                        base_url=base_url,
                        api_key=api_key,
                        model=image_model,
                        prompt=prompt,
                        n=n,
                        size=size,
                        response_format=response_format,
                        quality=quality,
                        style=style,
                        extra_body=extra_body,
                    )
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            # Success — clear cooldown
            if conn_id:
                await clear_connection_error(db, conn_id, image_model)
                await update_connection_usage(db, conn_id)

            # Track usage (image gen — no token counts)
            await save_request_tracking(
                db,
                provider=provider_id,
                model=image_model,
                connection_id=conn_id,
                endpoint="/v1/images/generations",
                latency_ttft=total_latency_ms,
                latency_total=total_latency_ms,
                request_body=body,
                provider_request_body={**body, "model": image_model},
                provider_response_body={"created": int(time.time()), "data": images},
                response_body={"created": int(time.time()), "data": images},
            )

            return JSONResponse(
                status_code=200,
                content={"created": int(time.time()), "data": images},
                headers={"X-Request-Id": request_id},
            )

        except NotImplementedError as e:
            return JSONResponse(
                status_code=501,
                content={"error": {"message": str(e)}},
                headers={"X-Request-Id": request_id},
            )
        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": e.response.text[:500]}},
                    headers={"X-Request-Id": request_id},
                )
            await _mark_conn_failed(
                db, conn_id, e.response.status_code,
                last_error["detail"], image_model, exclude_ids,
            )
            continue
        except httpx.ConnectError as e:
            last_error = {"status": 503, "detail": f"Upstream connect error: {e}"}
            if conn_id:
                exclude_ids.add(conn_id)
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)[:500]}
            if conn_id:
                exclude_ids.add(conn_id)
            continue

    # All connections failed
    err_msg: str = last_error.get("detail", "All image providers failed") if last_error else "No targets"
    err_status: int = last_error.get("status", 502) if last_error else 502
    return JSONResponse(
        status_code=err_status,
        content={"error": {"message": err_msg}},
        headers={"X-Request-Id": request_id},
    )
