"""Provider connection testing and batch test endpoints."""

import asyncio
import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import database
from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.models.proxy_pool import ProxyPool
from app.providers.provider import Provider
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.helpers import _get_base_url
from app.routers.providers.nodes import _build_node_handler
from app.routers.providers.validation import (
    _validate_custom_anthropic,
    _validate_custom_openai,
)
from app.schemas.provider import (
    BatchTestRequest,
    BatchTestResponse,
    BatchTestResult,
    ProviderValidateRequest,
    ProviderValidateResponse,
)
from app.services.outbound_proxy import (
    ProxyRequiredError,
    create_upstream_client,
    parse_proxy_usage,
    proxy_for_connection,
    resolve_proxy_url,
    use_outbound_proxy,
)
from app.services.proxy import resolve_model_to_targets


async def _test_provider_connection(conn: ProviderConnection, db: AsyncSession) -> dict:
    """Test a single provider connection using provider handler."""
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "") or data.get("accessToken", "")
    provider = conn.provider
    usage = parse_proxy_usage(data.get("proxyUsage"))
    pool = None
    if conn.proxy_pool_id:
        pool_result = await db.execute(
            select(ProxyPool).where(ProxyPool.id == conn.proxy_pool_id)
        )
        pool = pool_result.scalar_one_or_none()

    try:
        proxy_url = resolve_proxy_url(
            usage=usage,
            purpose="testConnection",
            pool=pool,
        )
    except ProxyRequiredError as exc:
        return {
            "valid": False,
            "error": str(exc),
            "latencyMs": 0,
            "models": None,
        }

    # Check if this is a compatible provider (node-based)
    node_result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == provider)
    )
    node = node_result.scalar_one_or_none()

    if node:
        node_data = {}
        try:
            node_data = json.loads(node.data) if node.data else {}
        except (json.JSONDecodeError, TypeError):
            pass
        node_base_url = node_data.get("baseUrl", "")
        handler = _build_node_handler(node.type, node_base_url, node.name, node.id)
        async with use_outbound_proxy(proxy_url):
            result = await handler.validate(api_key, data)
        return {"valid": result.valid, "error": result.error, "latencyMs": result.latency_ms, "models": result.models}

    # Built-in provider — use handler
    if not api_key:
        return {"valid": False, "error": "No API key configured for this connection", "latencyMs": 0, "models": None}

    try:
        p = Provider(provider)
        handler = p.handler()
        async with use_outbound_proxy(proxy_url):
            result = await handler.validate(api_key, data)
        return {"valid": result.valid, "error": result.error, "latencyMs": result.latency_ms, "models": result.models}
    except (ValueError, ModuleNotFoundError):
        return {"valid": False, "error": f"Unknown provider: {provider}", "latencyMs": 0, "models": None}


# --- Endpoints ---


@router.post("/providers/validate", response_model=ProviderValidateResponse)
async def validate_provider(
    body: ProviderValidateRequest,
    _user=Depends(get_current_user),
):
    """Validate provider credentials using provider handler."""
    # This pre-save payload has no connection or proxy pool to resolve.
    extra = body.providerSpecificData or {}

    # Check if this is a compatible provider node
    async with database.async_session() as db:
        node_result = await db.execute(
            select(ProviderNode).where(ProviderNode.id == body.provider)
        )
        node = node_result.scalar_one_or_none()

    if node:
        node_data = {}
        try:
            node_data = json.loads(node.data) if node.data else {}
        except (json.JSONDecodeError, TypeError):
            pass

        base_url = node_data.get("baseUrl", "")
        extra_headers = node_data.get("extraHeaders")

        if node.type == "anthropic-compatible":
            return await _validate_custom_anthropic(body.apiKey, base_url)
        else:
            return await _validate_custom_openai(body.apiKey, base_url, extra_headers)

    # Built-in provider
    try:
        p = Provider(body.provider)
        handler = p.handler()
        result = await handler.validate(body.apiKey, extra)
        return ProviderValidateResponse(
            valid=result.valid,
            error=result.error,
            models=result.models,
        )
    except (ValueError, ModuleNotFoundError):
        # Fallback for custom providers
        base_url = _get_base_url(body.provider, body.baseUrl, extra)
        if base_url:
            return await _validate_custom_openai(body.apiKey, base_url)
        return ProviderValidateResponse(valid=False, error=f"Unknown provider: {body.provider}")


@router.post("/providers/test-batch", response_model=BatchTestResponse)
async def test_batch(
    body: BatchTestRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test multiple provider connections by group (mode: provider, apikey, all)."""
    if not body.mode:
        raise HTTPException(status_code=400, detail="mode is required")

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.is_active == True)
    )
    all_connections = result.scalars().all()

    if body.mode == "provider" and body.providerId:
        connections_to_test = [c for c in all_connections if c.provider == body.providerId]
    elif body.mode == "apikey":
        connections_to_test = [c for c in all_connections if c.auth_type != "oauth"]
    elif body.mode == "all":
        connections_to_test = list(all_connections)
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid mode. Use: provider, apikey, all",
        )

    if not connections_to_test:
        return BatchTestResponse(
            mode=body.mode,
            providerId=body.providerId,
            results=[],
            summary={"total": 0, "passed": 0, "failed": 0},
            testedAt=datetime.now(timezone.utc).isoformat(),
        )

    results = []
    for conn in connections_to_test:
        try:
            test_result = await _test_provider_connection(conn, db)
            results.append(BatchTestResult(
                provider=conn.provider,
                connectionId=str(conn.id),
                connectionName=conn.name or conn.provider,
                authType=conn.auth_type,
                valid=test_result["valid"],
                latencyMs=test_result.get("latencyMs", 0),
                error=test_result.get("error"),
                testedAt=datetime.now(timezone.utc).isoformat(),
            ))
        except Exception as e:
            results.append(BatchTestResult(
                provider=conn.provider,
                connectionId=str(conn.id),
                connectionName=conn.name or conn.provider,
                authType=conn.auth_type,
                valid=False,
                latencyMs=0,
                error=str(e)[:200],
                testedAt=datetime.now(timezone.utc).isoformat(),
            ))

    return BatchTestResponse(
        mode=body.mode,
        providerId=body.providerId,
        results=results,
        testedAt=datetime.now(timezone.utc).isoformat(),
        summary={
            "total": len(results),
            "passed": sum(1 for r in results if r.valid),
            "failed": sum(1 for r in results if not r.valid),
        },
    )


class TestModelsRequest(BaseModel):
    """Request body for testing all models of a provider connection."""
    pass


@router.post("/providers/{connection_id}/test-models")
async def test_connection_models(
    connection_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test all models of a provider connection by making minimal chat completion calls."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    provider_id = conn.provider
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key = data.get("apiKey", "")
    alias = data.get("alias", provider_id)

    models = data.get("models", [])

    if not models:
        return {
            "provider": provider_id,
            "connectionId": connection_id,
            "results": [],
            "error": "No models configured for this provider",
        }

    async def ping_model(model_id: str) -> dict:
        start = time.monotonic()
        try:
            targets = await resolve_model_to_targets(db, f"{alias}/{model_id}")
            if not targets:
                return {
                    "modelId": model_id,
                    "ok": False,
                    "latencyMs": int((time.monotonic() - start) * 1000),
                    "error": f"No active connection found for model '{model_id}'",
                }

            target = targets[0]
            url = target.url
            headers = target.headers
            proxy_url = await proxy_for_connection(
                db, conn, "testModel",
            )

            async with create_upstream_client(
                proxy=proxy_url, timeout=15.0,
            ) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": target.model,
                        "max_tokens": 1,
                        "stream": False,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                latency = int((time.monotonic() - start) * 1000)
                ok = resp.status_code in (200, 400)
                error = None if ok else f"HTTP {resp.status_code}"
                if not ok:
                    try:
                        err_data = resp.json()
                        error = err_data.get("error", {}).get("message", error)
                    except Exception:
                        pass
                return {"modelId": model_id, "ok": ok, "latencyMs": latency, "error": error}
        except httpx.TimeoutException:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": "Timeout"}
        except httpx.ConnectError:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": "Connection failed"}
        except Exception as e:
            return {"modelId": model_id, "ok": False, "latencyMs": int((time.monotonic() - start) * 1000), "error": str(e)[:200]}

    model_ids = [m if isinstance(m, str) else m.get("id", "") for m in models]
    model_ids = [m for m in model_ids if m]

    if not model_ids:
        return {
            "provider": provider_id,
            "connectionId": connection_id,
            "results": [],
            "error": "No valid model IDs found",
        }

    first_result = await ping_model(model_ids[0])
    results = [first_result]

    if len(model_ids) > 1:
        rest_results = await asyncio.gather(*[ping_model(m) for m in model_ids[1:]])
        results.extend(rest_results)

    return {
        "provider": provider_id,
        "connectionId": connection_id,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("ok")),
            "failed": sum(1 for r in results if not r.get("ok")),
        },
    }
