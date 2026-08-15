"""Provider model fetching and clearing endpoints."""

import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.models.settings import SettingsModel
from app.providers.provider import Provider
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.services.proxy import _resolve_provider_alias
from app.routers.providers.constants import normalize_models_list
from app.routers.providers.nodes import _build_node_handler
from app.services.outbound_proxy import proxy_for_connection, use_outbound_proxy


# ── Node-based model fetching ─────────────────────────────────────────────

async def _fetch_node_models(node: ProviderNode, api_key: str) -> list[dict]:
    """Fetch models from a custom compatible node (openai/anthropic)."""
    node_data: dict = json.loads(node.data) if node.data else {}
    node_base_url: str = node_data.get("baseUrl", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="No API key configured")
    if not node_base_url:
        raise HTTPException(status_code=400, detail="No base URL configured")

    handler = _build_node_handler(node.type, node_base_url, node.name, node.id)
    try:
        models_raw: list[dict] = await handler.fetch_models(api_key, node_data)
        return models_raw
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {node_base_url}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")


# ── Built-in provider model fetching ──────────────────────────────────────

async def _fetch_builtin_models(
    provider: str, api_key: str, data: dict,
) -> list[dict]:
    """Fetch models from a built-in provider using the Provider handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
    except (ValueError, ModuleNotFoundError):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    token: str = data.get("accessToken") or api_key

    # noAuth providers (like OpenCode Free) don't need a token
    if not token and not p.config().NO_AUTH:
        raise HTTPException(status_code=401, detail="No valid token found")

    try:
        return await handler.fetch_models(token, data)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot connect to {provider}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection timed out")
    except httpx.HTTPStatusError as e:
        try:
            error_body = e.response.json()
            error_message = error_body.get("message", error_body.get("errorMessage", str(e)))
        except Exception:
            error_message = str(e)
        raise HTTPException(status_code=e.response.status_code, detail=error_message)




# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/providers/{provider_id}/models/list")
async def list_provider_models(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """List all stored models for a provider (from DB, no upstream call).

    provider_id can be a provider ID or alias.
    """
    from app.services.proxy import _resolve_provider_alias
    from app.services.provider_models_store import (
        list_provider_models as list_catalog,
        uses_model_catalog_table,
    )
    resolved = _resolve_provider_alias(provider_id)
    if uses_model_catalog_table(resolved):
        all_models = await list_catalog(db, resolved)
        return {
            "provider": resolved,
            "count": len(all_models),
            "models": all_models,
        }
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == resolved)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    all_models: list[dict] = []
    seen: set[str] = set()
    for conn in connections:
        blob = json.loads(conn.data) if conn.data else {}
        for m in blob.get("models", []):
            mid = m if isinstance(m, str) else m.get("id", "")
            if mid and mid not in seen:
                seen.add(mid)
                mtype = "llm"
                if isinstance(m, dict) and "type" in m:
                    mtype = m["type"]
                elif mid in blob.get("modelTypes", {}):
                    mtype = blob["modelTypes"][mid]
                all_models.append({"id": mid, "type": mtype})
    return {
        "provider": resolved,
        "count": len(all_models),
        "models": all_models,
    }


@router.get("/providers/{conn_id}/models")
async def fetch_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Fetch available models from a provider's API using the connection's credentials."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    api_key: str = data.get("apiKey", "")
    provider: str = conn.provider

    # Check if this is a compatible provider (node-based)
    node_result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == provider)
    )
    node: ProviderNode | None = node_result.scalar_one_or_none()

    proxy_url = await proxy_for_connection(db, conn, "upstream")
    async with use_outbound_proxy(proxy_url):
        if node:
            models: list[dict] = await _fetch_node_models(node, api_key)
        else:
            models = await _fetch_builtin_models(provider, api_key, data)

    # Persist catalog (per provider), not on this connection blob.
    stored = [
        {"id": m.get("id"), "type": m.get("type", "llm")}
        for m in models if m.get("id")
    ]
    from app.providers.provider import Provider as P
    from app.services.provider_models_store import (
        replace_provider_models,
        uses_model_catalog_table,
    )
    if uses_model_catalog_table(provider):
        force = False
        try:
            force = bool(
                P(provider).config().SYNC_DISABLED_WITH_MODEL_LIST
            )
        except (ValueError, ModuleNotFoundError):
            force = False
        await replace_provider_models(
            db, provider, stored, force_enable=force,
        )
    else:
        data["models"] = stored
        conn.data = json.dumps(data)
    await db.flush()
    return {
        "provider": provider,
        "connectionId": str(conn.id),
        "models": models,
    }


@router.delete("/providers/{conn_id}/models")
async def clear_provider_models(
    conn_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Clear all stored models from a provider connection.

    Disabled models history is preserved in settings so that
    Fetch Models can restore the enable/disable state.
    """
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    current_models: list = data.get("models", [])
    cleared_count: int = len(current_models) if isinstance(current_models, list) else 0

    data["models"] = []
    conn.data = json.dumps(data)

    # Note: disabled models history is preserved in settings
    # so that Fetch Models can restore the enable/disable state

    await db.flush()
    return {"ok": True, "clearedCount": cleared_count}


@router.patch("/providers/{conn_id}/models/type")
async def change_model_type(
    conn_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> dict:
    """Override the type for a specific model in a provider connection."""
    VALID_TYPES: set[str] = {
        "llm", "embedding", "tts", "stt", "image", "imageToText",
        "video", "music", "webSearch", "webFetch",
    }

    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == conn_id)
    )
    conn: ProviderConnection | None = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    model_id: str | None = body.get("model_id")
    new_type: str | None = body.get("type")
    if not model_id or not new_type:
        raise HTTPException(status_code=400, detail="model_id and type are required")
    if new_type not in VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{new_type}'. Valid: {', '.join(sorted(VALID_TYPES))}",
        )

    data: dict = {}
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    models: list = data.get("models", [])
    normalized: list[dict] = normalize_models_list(models)

    found: bool = False
    for m in normalized:
        if isinstance(m, dict) and m.get("id") == model_id:
            m["type"] = new_type
            found = True
            break

    if not found:
        normalized.append({"id": model_id, "type": new_type})

    data["models"] = normalized
    data.pop("modelTypes", None)
    conn.data = json.dumps(data)
    await db.flush()

    return {"ok": True, "model_id": model_id, "type": new_type}
