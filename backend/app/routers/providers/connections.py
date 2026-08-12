"""Provider Connection CRUD endpoints."""

import json
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.constants import SUGGESTED_MODELS_FILTERS, normalize_models_list
from app.routers.providers.helpers import _get_provider_config
from app.routers.providers.helpers import (
    _connection_to_out,
    _next_provider_priority,
    _normalize_proxy_config,
    _normalize_proxy_pool_id,
    _priorities_need_renumber,
    _renumber_provider_priorities,
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


def _models_union_from_data_blobs(data_blobs: list[str | None]) -> list:
    """Build unique model list from connection data JSON blobs."""
    seen: set[str] = set()
    models: list = []
    for raw in data_blobs:
        try:
            data = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            continue
        for m in data.get("models") or []:
            mid = m if isinstance(m, str) else (m or {}).get("id", "")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            models.append(m)
    return normalize_models_list(models)


@router.get("/providers", response_model=list[ProviderConnectionOut])
async def list_providers(
    kind: str | None = Query(
        None, description="Filter by service kind (e.g. llm, embedding, tts)"
    ),
    provider: str | None = Query(
        None, description="Filter by provider id (e.g. mistral)"
    ),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List provider connections (sensitive data hidden).

    When `kind` is provided, only return connections for providers that support
    that service kind (based on provider config SERVICE_KINDS). Providers
    without explicit serviceKinds default to ["llm"].
    Prefer `/providers/by-provider/{id}/connections` for detail pages.
    """
    stmt = select(ProviderConnection).order_by(
        ProviderConnection.provider, ProviderConnection.priority
    )
    if provider is not None:
        stmt = stmt.where(ProviderConnection.provider == provider)
    result = await db.execute(stmt)
    connections = result.scalars().all()

    if kind is not None:
        kind_cache: dict[str, bool] = {}

        def _matches_kind(conn: ProviderConnection) -> bool:
            cached = kind_cache.get(conn.provider)
            if cached is not None:
                return cached
            defaults = _get_provider_config(conn.provider)
            kinds = defaults.get("serviceKinds", ["llm"])
            ok = kind in kinds
            kind_cache[conn.provider] = ok
            return ok

        connections = [c for c in connections if _matches_kind(c)]

    return [_connection_to_out(c) for c in connections]


@router.get("/providers/by-provider/{provider_id}/connections")
async def list_provider_connections(
    provider_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    include_ids: bool = Query(
        False,
        description="Include all connectionIds (select-all / bulk ops)",
    ),
    include_models: bool = Query(
        True,
        description="Include models union once (not per connection)",
    ),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Paginated connections for one provider (detail page).

    Avoids downloading every connection for every provider. Models are
    returned once at the top level; each item.models is omitted/empty.
    """
    where = ProviderConnection.provider == provider_id

    # Heal legacy duplicate/gapped priorities once (page 1 only)
    if page == 1 and await _priorities_need_renumber(db, provider_id):
        await _renumber_provider_priorities(db, provider_id)
        await db.flush()

    total = await db.scalar(
        select(func.count()).select_from(ProviderConnection).where(where)
    )
    total_i = int(total or 0)

    offset = (page - 1) * page_size
    page_result = await db.execute(
        select(ProviderConnection)
        .where(where)
        .order_by(ProviderConnection.priority, ProviderConnection.id)
        .offset(offset)
        .limit(page_size)
    )
    page_conns = page_result.scalars().all()

    items: list[dict] = []
    for conn in page_conns:
        out = _connection_to_out(conn)
        out["models"] = []
        items.append(out)

    models: list = []
    if include_models and total_i > 0:
        blobs = await db.execute(
            select(ProviderConnection.data).where(where)
        )
        models = _models_union_from_data_blobs(
            list(blobs.scalars().all())
        )

    payload: dict = {
        "provider": provider_id,
        "total": total_i,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
    if include_models:
        payload["models"] = models
    if include_ids:
        id_rows = await db.execute(
            select(ProviderConnection.id)
            .where(where)
            .order_by(ProviderConnection.priority, ProviderConnection.id)
        )
        payload["connectionIds"] = [
            str(i) for i in id_rows.scalars().all()
        ]
    return payload


@router.patch("/providers/by-provider/{provider_id}/models")
async def set_provider_models(
    provider_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Set models JSON on all connections of a provider (one round-trip)."""
    if "models" not in body:
        raise HTTPException(status_code=400, detail="models is required")
    models = normalize_models_list(body.get("models") or [])

    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider == provider_id
        )
    )
    connections = result.scalars().all()
    if not connections:
        raise HTTPException(status_code=404, detail="No connections for provider")

    for conn in connections:
        try:
            data = json.loads(conn.data) if conn.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        data["models"] = models
        conn.data = json.dumps(data)
        invalidate_connection_cache(str(conn.id))

    await db.commit()
    return {
        "provider": provider_id,
        "updated": len(connections),
        "models": models,
    }


@router.delete("/providers/by-provider/{provider_id}/models")
async def clear_provider_models_bulk(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Clear models on all connections of a provider."""
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider == provider_id
        )
    )
    connections = result.scalars().all()
    if not connections:
        raise HTTPException(status_code=404, detail="No connections for provider")

    for conn in connections:
        try:
            data = json.loads(conn.data) if conn.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        data["models"] = []
        conn.data = json.dumps(data)
        invalidate_connection_cache(str(conn.id))

    await db.commit()
    return {"provider": provider_id, "updated": len(connections), "models": []}


@router.post("/providers/{conn_id}/reorder")
async def reorder_connection(
    conn_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Swap priority with neighbor (up/down) for same provider."""
    direction = body.get("direction")
    if direction not in ("up", "down"):
        raise HTTPException(
            status_code=400, detail="direction must be 'up' or 'down'"
        )

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    siblings = (
        await db.execute(
            select(ProviderConnection)
            .where(ProviderConnection.provider == conn.provider)
            .order_by(ProviderConnection.priority, ProviderConnection.id)
        )
    ).scalars().all()

    idx = next((i for i, c in enumerate(siblings) if c.id == conn.id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Connection not found")

    swap_idx = idx - 1 if direction == "up" else idx + 1
    if swap_idx < 0 or swap_idx >= len(siblings):
        return {"moved": False, "reason": "already_at_edge"}

    ordered = list(siblings)
    mover = ordered.pop(idx)
    neighbor = siblings[swap_idx]
    ordered.insert(swap_idx, mover)
    for i, row in enumerate(ordered):
        if row.priority != i:
            row.priority = i
            invalidate_connection_cache(str(row.id))

    await db.commit()
    return {
        "moved": True,
        "a": str(mover.id),
        "b": str(neighbor.id),
        "priorities": {
            str(row.id): row.priority for row in ordered
        },
    }


@router.get("/providers/overview")
async def providers_overview(
    kind: str | None = Query(
        "llm",
        description="Filter by service kind (default llm)",
    ),
    include_ids: bool = Query(
        False,
        description="Include connectionIds (for batch test); omit on list load",
    ),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Lightweight per-provider stats for /providers list page.

    Avoids returning thousands of full connection payloads (models,
    providerSpecificData, etc.). Pass include_ids=true when the client
    needs connection UUIDs for batch actions.
    """
    result = await db.execute(
        select(ProviderConnection).order_by(
            ProviderConnection.provider, ProviderConnection.priority
        )
    )
    connections = result.scalars().all()

    kind_cache: dict[str, bool] = {}

    def _matches_kind(provider: str) -> bool:
        cached = kind_cache.get(provider)
        if cached is not None:
            return cached
        defaults = _get_provider_config(provider)
        kinds = defaults.get("serviceKinds", ["llm"])
        ok = kind is None or kind in kinds
        kind_cache[provider] = ok
        return ok

    stats: dict[str, dict] = {}
    for conn in connections:
        if not _matches_kind(conn.provider):
            continue

        data: dict = {}
        try:
            data = json.loads(conn.data) if conn.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}

        entry = stats.get(conn.provider)
        if entry is None:
            entry = {
                "total": 0,
                "connected": 0,
                "error": 0,
                "allDisabled": True,
                "errorCode": None,
                "errorAt": None,
            }
            if include_ids:
                entry["connectionIds"] = []
            stats[conn.provider] = entry

        entry["total"] += 1
        if include_ids:
            entry["connectionIds"].append(str(conn.id))
        if conn.is_active:
            entry["allDisabled"] = False

        status = data.get("testStatus")
        if status in ("active", "success", "connected"):
            entry["connected"] += 1
        elif status in ("error", "expired", "unavailable"):
            entry["error"] += 1
            err_at = data.get("lastErrorAt")
            prev_at = entry.get("errorAt")
            if err_at and (not prev_at or str(err_at) > str(prev_at)):
                entry["errorAt"] = err_at
                entry["errorCode"] = (
                    data.get("lastErrorType")
                    or data.get("errorCode")
                    or data.get("lastError")
                )

    for entry in stats.values():
        if entry["total"] == 0:
            entry["allDisabled"] = False

    return {"stats": stats}


@router.patch("/providers/by-provider/{provider_id}/active")
async def set_provider_connections_active(
    provider_id: str,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Set is_active for all connections of a provider (list-page toggle)."""
    if "is_active" not in body and "isActive" not in body:
        raise HTTPException(status_code=400, detail="is_active is required")
    is_active = body.get("is_active", body.get("isActive"))
    if not isinstance(is_active, bool):
        raise HTTPException(status_code=400, detail="is_active must be boolean")

    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider == provider_id
        )
    )
    connections = result.scalars().all()
    if not connections:
        raise HTTPException(status_code=404, detail="No connections for provider")

    for conn in connections:
        conn.is_active = is_active
        invalidate_connection_cache(str(conn.id))

    await db.commit()
    return {
        "provider": provider_id,
        "is_active": is_active,
        "updated": len(connections),
    }


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
        priority=await _next_provider_priority(db, body.provider),
        proxy_pool_id=proxy_pool_id,
        data=json.dumps(data),
    )
    db.add(conn)
    await db.flush()
    await _renumber_provider_priorities(db, body.provider)
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
    await _renumber_provider_priorities(db, conn.provider)
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
    provider = conn.provider
    await db.delete(conn)
    await db.flush()
    await _renumber_provider_priorities(db, provider)


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
    providers_to_fix: set[str] = set()
    if ids:
        if not isinstance(ids, list):
            raise HTTPException(
                status_code=400, detail="'ids' must be a list",
            )
        existing = (
            await db.execute(
                select(ProviderConnection).where(
                    ProviderConnection.id.in_(ids)
                )
            )
        ).scalars().all()
        providers_to_fix = {c.provider for c in existing}
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

    await db.flush()
    for pid in providers_to_fix:
        await _renumber_provider_priorities(db, pid)
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
