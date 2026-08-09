"""Provider Connection CRUD endpoints."""

import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import SUGGESTED_MODELS_FILTERS, normalize_models_list
from app.routers.providers.helpers import _get_provider_config
from app.routers.providers.helpers import (
    _connection_to_out,
    _normalize_proxy_config,
    _normalize_proxy_pool_id,
    _sanitize_connection,
)
from app.routers.providers.validation import _validate_provider
from app.services.proxy import invalidate_connection_cache
from app.schemas.provider import (
    ProviderConnectionCreate,
    ProviderConnectionOut,
    ProviderConnectionUpdate,
    SuggestedModelsResponse,
    ProviderTestResponse,
)


@router.get("/providers", response_model=list[ProviderConnectionOut])
async def list_providers(
    kind: str | None = Query(None, description="Filter by service kind (e.g. llm, embedding, tts)"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all provider connections (sensitive data hidden).

    When `kind` is provided, only return connections for providers that support
    that service kind (based on provider config SERVICE_KINDS). Providers
    without explicit serviceKinds default to ["llm"].
    """
    result = await db.execute(
        select(ProviderConnection).order_by(
            ProviderConnection.provider, ProviderConnection.priority
        )
    )
    connections = result.scalars().all()

    if kind is not None:
        def _matches_kind(conn):
            defaults = _get_provider_config(conn.provider)
            kinds = defaults.get("serviceKinds", ["llm"])
            return kind in kinds
        connections = [c for c in connections if _matches_kind(c)]

    return [_connection_to_out(c) for c in connections]


@router.get("/providers/client")
async def list_providers_client(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List provider connections for dashboard UI (whitelist only, no sensitive data)."""
    result = await db.execute(
        select(ProviderConnection).order_by(
            ProviderConnection.provider, ProviderConnection.priority
        )
    )
    connections = result.scalars().all()
    return {"connections": [_sanitize_connection(_connection_to_out(c)) for c in connections]}


@router.post(
    "/providers",
    response_model=ProviderConnectionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    body: ProviderConnectionCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Create a new provider connection.

    Handles proxy config, proxy pool validation, and provider-specific data
    for compatible providers (OpenAI/Anthropic node-based).
    """
    # Normalize proxy config
    proxy_config = _normalize_proxy_config(body.model_dump(exclude_none=True))
    if proxy_config.get("error"):
        raise HTTPException(status_code=400, detail=proxy_config["error"])

    # Validate proxy pool
    proxy_pool_result = await _normalize_proxy_pool_id(db, body.proxyPoolId)
    if proxy_pool_result.get("error"):
        raise HTTPException(status_code=400, detail=proxy_pool_result["error"])
    proxy_pool_id = proxy_pool_result.get("proxyPoolId")

    # Validate provider-specific required fields
    if body.provider == "azure":
        psd = body.providerSpecificData or {}
        if not psd.get("azureEndpoint"):
            raise HTTPException(status_code=400, detail="azureEndpoint is required for Azure OpenAI")
        if not psd.get("deployment"):
            raise HTTPException(status_code=400, detail="deployment is required for Azure OpenAI")
    if body.provider == "cloudflare-ai":
        psd = body.providerSpecificData or {}
        if not psd.get("accountId"):
            raise HTTPException(status_code=400, detail="accountId is required for Cloudflare AI")

    # Build the data JSON blob
    data = {
        "apiKey": body.apiKey,
        "models": normalize_models_list(body.models) if body.models else [],
        "roundRobin": body.round_robin,
    }

    if body.displayName:
        data["displayName"] = body.displayName
    if body.globalPriority is not None:
        data["globalPriority"] = body.globalPriority
    if body.defaultModel:
        data["defaultModel"] = body.defaultModel

    # Store base URL if provided or use default
    if body.baseUrl:
        data["baseUrl"] = body.baseUrl
    else:
        defaults = _get_provider_config(body.provider)
        default_url = defaults.get("baseUrl")
        if default_url:
            data["baseUrl"] = default_url

    # Handle compatible providers — look up node and set providerSpecificData
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
        psd = {
            "prefix": node_data.get("prefix"),
            "baseUrl": node_data.get("baseUrl"),
            "nodeName": node.name,
        }
        if node.type == "openai-compatible":
            psd["apiType"] = node_data.get("apiType")
        data.update(psd)

    # Store provider-specific data
    if body.providerSpecificData:
        data.update(body.providerSpecificData)

    # Store proxy config in data
    data["connectionProxyEnabled"] = proxy_config["connectionProxyEnabled"]
    data["connectionProxyUrl"] = proxy_config["connectionProxyUrl"]
    data["connectionNoProxy"] = proxy_config["connectionNoProxy"]

    # Determine test status
    test_status = body.testStatus or "unknown"
    is_no_auth = body.noAuth is True or body.auth_type == "free"
    if is_no_auth:
        test_status = "connected"
    elif body.apiKey and test_status == "unknown":
        # Auto-validate on create using handler dispatch
        try:
            extra = body.providerSpecificData or {}
            vr = await _validate_provider(body.provider, body.apiKey, extra)
            if vr:
                test_status = "connected" if vr.valid else "error"
        except Exception:
            test_status = "untested"

    data["testStatus"] = test_status

    conn = ProviderConnection(
        provider=body.provider,
        auth_type=body.auth_type,
        name=body.name,
        priority=body.priority,
        proxy_pool_id=proxy_pool_id,
        data=json.dumps(data),
    )
    db.add(conn)
    await db.flush()
    await db.refresh(conn)
    return _connection_to_out(conn)


@router.get("/providers/suggested-models", response_model=SuggestedModelsResponse)
async def get_suggested_models(
    url: str = Query(..., description="URL to fetch models from"),
    type: str = Query(..., description="Filter type (e.g. openrouter-free, opencode-free)"),
    _user=Depends(get_current_user),
):
    """Fetch and filter suggested models from a provider's model list endpoint."""
    filter_fn = SUGGESTED_MODELS_FILTERS.get(type)
    if not filter_fn:
        raise HTTPException(status_code=400, detail="Unknown filter type")

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code >= 400:
                return SuggestedModelsResponse(data=[])
            json_data = resp.json()
            raw = json_data.get("data") or json_data.get("models") or json_data
            if not isinstance(raw, list):
                raw = []
            data = filter_fn(raw)
            return SuggestedModelsResponse(data=data)
        except Exception:
            return SuggestedModelsResponse(data=[])


# --- Provider CRUD (parameterized routes AFTER static routes) ---


@router.get("/providers/{conn_id}", response_model=ProviderConnectionOut)
async def get_provider(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get a single provider connection by ID."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider connection not found",
        )
    return _connection_to_out(conn)


@router.patch("/providers/{conn_id}", response_model=ProviderConnectionOut)
async def update_provider(
    conn_id: str,
    body: ProviderConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update a provider connection.

    Supports merging providerSpecificData and proxy config,
    matching the original Next.js update behavior.
    """
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider connection not found",
        )

    body_dict = body.model_dump(exclude_none=True)

    # Validate proxy config if provided
    has_proxy_field = any(
        k in body_dict for k in ("connectionProxyEnabled", "connectionProxyUrl", "connectionNoProxy")
    )
    if has_proxy_field:
        proxy_config = _normalize_proxy_config(body_dict)
        if proxy_config.get("error"):
            raise HTTPException(status_code=400, detail=proxy_config["error"])

    # Validate proxy pool if provided
    if body.proxyPoolId is not None:
        proxy_pool_result = await _normalize_proxy_pool_id(db, body.proxyPoolId)
        if proxy_pool_result.get("error"):
            raise HTTPException(status_code=400, detail=proxy_pool_result["error"])
        conn.proxy_pool_id = proxy_pool_result.get("proxyPoolId")

    # Update simple model fields
    if body.name is not None:
        conn.name = body.name
    if body.is_active is not None:
        conn.is_active = body.is_active
    if body.priority is not None:
        conn.priority = body.priority

    # Update data JSON blob fields
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    if body.apiKey is not None:
        data["apiKey"] = body.apiKey
    if body.models is not None:
        data["models"] = normalize_models_list(body.models) if body.models else []
    if body.round_robin is not None:
        data["roundRobin"] = body.round_robin
    if body.baseUrl is not None:
        data["baseUrl"] = body.baseUrl
    if body.displayName is not None:
        data["displayName"] = body.displayName
    if body.globalPriority is not None:
        data["globalPriority"] = body.globalPriority
    if body.defaultModel is not None:
        data["defaultModel"] = body.defaultModel
    if body.testStatus is not None:
        data["testStatus"] = body.testStatus
    if body.lastError is not None:
        data["lastError"] = body.lastError
    if body.lastErrorAt is not None:
        data["lastErrorAt"] = body.lastErrorAt

    # Merge providerSpecificData
    if body.providerSpecificData is not None:
        data.update(body.providerSpecificData)

    # Merge proxy config if provided
    if has_proxy_field:
        proxy_config = _normalize_proxy_config(body_dict)
        if not proxy_config.get("error"):
            data["connectionProxyEnabled"] = proxy_config["connectionProxyEnabled"]
            data["connectionProxyUrl"] = proxy_config["connectionProxyUrl"]
            data["connectionNoProxy"] = proxy_config["connectionNoProxy"]

    conn.data = json.dumps(data)

    await db.flush()
    await db.refresh(conn)

    # Invalidate proxy cache so next request sees updated is_active state
    invalidate_connection_cache(conn.provider)

    return _connection_to_out(conn)


@router.delete("/providers/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a provider connection."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider connection not found",
        )
    await db.delete(conn)


@router.post("/providers/bulk-delete")
async def bulk_delete_providers(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete multiple provider connections at once.

    Body: ``{"ids": ["uuid1", "uuid2", ...]}``
    or ``{"provider": "alims-intl"}`` to wipe all for a provider.
    """
    ids = payload.get("ids")
    provider = payload.get("provider")

    if not ids and not provider:
        raise HTTPException(
            status_code=400,
            detail="Provide 'ids' (list) or 'provider' (string)",
        )

    deleted = 0
    if ids:
        if not isinstance(ids, list):
            raise HTTPException(
                status_code=400, detail="'ids' must be a list",
            )
        result = await db.execute(
            delete(ProviderConnection).where(
                ProviderConnection.id.in_(ids)
            )
        )
        deleted = result.rowcount
    else:
        result = await db.execute(
            delete(ProviderConnection).where(
                ProviderConnection.provider == provider
            )
        )
        deleted = result.rowcount

    await db.commit()
    return {"deleted": deleted}


@router.post("/providers/{conn_id}/test", response_model=ProviderTestResponse)
async def test_provider(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test a provider connection by making a lightweight API call."""
    from app.routers.providers.testing import _test_provider_connection

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider connection not found",
        )

    test_result = await _test_provider_connection(conn, db)

    # Update test status and save models in the data blob
    data = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    data["testStatus"] = "connected" if test_result["valid"] else "error"
    if not test_result["valid"] and test_result.get("error"):
        data["lastError"] = test_result["error"]
        data["lastErrorAt"] = datetime.now(timezone.utc).isoformat()

    # Save models if test succeeded and models were returned
    if test_result["valid"] and test_result.get("models"):
        data["models"] = normalize_models_list(test_result["models"])

    conn.data = json.dumps(data)
    await db.flush()

    return ProviderTestResponse(
        valid=test_result["valid"],
        error=test_result.get("error"),
        refreshed=False,
        latencyMs=test_result.get("latencyMs"),
        models=test_result.get("models"),
    )
