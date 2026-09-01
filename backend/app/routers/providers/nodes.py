"""Provider Node CRUD and validation endpoints."""

import json
import time
import uuid as _uuid
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.providers.base import BaseProviderConfig, BaseProviderHandler
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.helpers import _node_to_out
from app.services.provider_aliases import refresh_from_db
from app.services.proxy import invalidate_connection_cache
from app.schemas.provider import (
    ProviderNodeCreate,
    ProviderNodeOut,
    ProviderNodeUpdate,
    ProviderNodeValidateRequest,
    ProviderNodeValidateResponse,
)


def _build_node_handler(node_type: str, base_url: str, node_name: str = "", node_id: str = "") -> BaseProviderHandler:
    """Build a BaseProviderHandler from node type and base URL.

    Used for node validation and connection testing.
    """
    if node_type == "anthropic-compatible":
        normalized = base_url.rstrip("/")
        if normalized.endswith("/messages"):
            normalized = normalized[:-9]
        config = BaseProviderConfig(
            PROVIDER_NAME=node_name or node_id,
            PROVIDER_ID=node_id,
            ALIAS=node_id,
            BASE_URL=normalized,
            AUTH_HEADER="x-api-key",
            AUTH_PREFIX="",
            EXTRA_HEADERS={"anthropic-version": "2023-06-01"},
        )
    else:
        config = BaseProviderConfig(
            PROVIDER_NAME=node_name or node_id,
            PROVIDER_ID=node_id,
            ALIAS=node_id,
            BASE_URL=base_url,
        )
    return BaseProviderHandler(config)


def stale_model_lock_keys(
    data: dict,
    *,
    node_id: str,
    old_prefix: str = "",
) -> list[str]:
    """Cooldown keys that still embed the node id or previous prefix."""
    needles: list[str] = []
    nid = (node_id or "").strip()
    if nid:
        needles.append(f"modelLock_{nid}/")
    prev = (old_prefix or "").strip()
    if prev:
        needles.append(f"modelLock_{prev}/")
    stale: list[str] = []
    for key in data:
        if not isinstance(key, str) or not key.startswith("modelLock_"):
            continue
        if any(key.startswith(n) for n in needles):
            stale.append(key)
    return stale


@router.get("/provider-nodes", response_model=list[ProviderNodeOut])
async def list_provider_nodes(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all custom provider nodes."""
    result = await db.execute(
        select(ProviderNode).order_by(ProviderNode.created_at.desc())
    )
    nodes = result.scalars().all()
    return [_node_to_out(n) for n in nodes]


@router.post(
    "/provider-nodes",
    response_model=ProviderNodeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_node(
    body: ProviderNodeCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Create a custom provider node.

    If ``id`` is omitted, the server generates one using the same prefix scheme
    as the original Next.js implementation:
      - openai-compatible: ``openai-compatible-{apiType}-{uuid}``
      - anthropic-compatible: ``anthropic-compatible-{uuid}``
      - custom-embedding: ``custom-embedding-{uuid}``
    """
    # Validate required fields (matching original Next.js validation)
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if not body.prefix or not body.prefix.strip():
        raise HTTPException(status_code=400, detail="Prefix is required")

    node_type = body.type or "openai-compatible"

    if node_type == "openai-compatible":
        if not body.api_type or body.api_type not in ("chat", "responses"):
            raise HTTPException(status_code=400, detail="Invalid OpenAI compatible API type")

    node_id = body.id
    if not node_id:
        uid = _uuid.uuid4().hex[:12]
        if node_type == "openai-compatible":
            api_t = body.api_type or "chat"
            node_id = f"openai-compatible-{api_t}-{uid}"
        elif node_type == "anthropic-compatible":
            node_id = f"anthropic-compatible-{uid}"
        elif node_type == "custom-embedding":
            node_id = f"custom-embedding-{uid}"
        else:
            node_id = f"{node_type}-{uid}"

    # Sanitize base URL (now required by schema)
    data = {}
    sanitized = body.base_url.strip().rstrip("/")
    if node_type == "anthropic-compatible" and sanitized.endswith("/messages"):
        sanitized = sanitized[:-9]
    if node_type == "custom-embedding" and sanitized.endswith("/embeddings"):
        sanitized = sanitized[: -len("/embeddings")]
    data["baseUrl"] = sanitized

    if body.prefix:
        data["prefix"] = body.prefix.strip()
    if body.api_type:
        data["apiType"] = body.api_type

    node = ProviderNode(
        id=node_id,
        type=node_type,
        name=body.name.strip(),
        data=json.dumps(data),
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return _node_to_out(node)


@router.delete(
    "/provider-nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider_node(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a custom provider node and its associated connections."""
    result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == node_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider node not found",
        )

    # Cascade: delete provider connections referencing this node
    conn_result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.provider == node_id)
    )
    for conn in conn_result.scalars().all():
        await db.delete(conn)

    await db.delete(node)


@router.put(
    "/provider-nodes/{node_id}",
    response_model=ProviderNodeOut,
)
async def update_provider_node(
    node_id: str,
    body: ProviderNodeUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update a custom provider node.

    When the node's prefix/baseUrl changes, all connections that reference this
    node have their ``providerSpecificData`` updated to stay in sync (matching
    the original Next.js behaviour).
    """
    result = await db.execute(
        select(ProviderNode).where(ProviderNode.id == node_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider node not found",
        )

    # Validate required fields (matching original Next.js validation)
    if body.name is not None and not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if body.prefix is not None and not body.prefix.strip():
        raise HTTPException(status_code=400, detail="Prefix is required")
    if node.type == "openai-compatible" and body.api_type is not None:
        if body.api_type not in ("chat", "responses"):
            raise HTTPException(status_code=400, detail="Invalid OpenAI compatible API type")

    # Parse existing data blob
    data = {}
    try:
        data = json.loads(node.data) if node.data else {}
    except (json.JSONDecodeError, TypeError):
        pass

    old_prefix = str(data.get("prefix") or "").strip()

    # Apply updates
    if body.name is not None:
        node.name = body.name.strip()
    if body.prefix is not None:
        data["prefix"] = body.prefix.strip()
    if body.base_url is not None:
        sanitized = body.base_url.strip().rstrip("/")
        # Anthropic: strip trailing /messages
        if node.type == "anthropic-compatible" and sanitized.endswith("/messages"):
            sanitized = sanitized[:-9]
        # Custom embedding: strip trailing /embeddings
        if node.type == "custom-embedding" and sanitized.endswith("/embeddings"):
            sanitized = sanitized[: -len("/embeddings")]
        data["baseUrl"] = sanitized
    if body.api_type is not None and node.type == "openai-compatible":
        data["apiType"] = body.api_type

    node.data = json.dumps(data)
    await db.flush()
    await db.refresh(node)

    # Sync connections that reference this node
    conn_result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.provider == node_id)
    )
    connections = conn_result.scalars().all()
    for conn in connections:
        conn_data = {}
        try:
            conn_data = json.loads(conn.data) if conn.data else {}
        except (json.JSONDecodeError, TypeError):
            pass
        psd = conn_data.get("providerSpecificData") or {}
        if body.prefix is not None:
            psd["prefix"] = body.prefix
        if body.base_url is not None:
            psd["baseUrl"] = data.get("baseUrl", "")
        if node.type == "openai-compatible" and body.api_type is not None:
            psd["apiType"] = body.api_type
        if body.name is not None:
            psd["nodeName"] = body.name
        conn_data["providerSpecificData"] = psd
        new_prefix = (
            body.prefix.strip() if body.prefix is not None else ""
        )
        drop_prefix = old_prefix if (
            new_prefix and new_prefix != old_prefix
        ) else ""
        for key in stale_model_lock_keys(
            conn_data, node_id=node_id, old_prefix=drop_prefix,
        ):
            conn_data.pop(key, None)
        conn.data = json.dumps(conn_data)
        invalidate_connection_cache(str(conn.id))

    await db.flush()
    await refresh_from_db(db)
    invalidate_connection_cache(node_id)
    return _node_to_out(node)


# --- Provider Nodes Validate ---


@router.post("/provider-nodes/validate", response_model=ProviderNodeValidateResponse)
async def validate_provider_node(
    body: ProviderNodeValidateRequest,
    _user=Depends(get_current_user),
):
    """Validate an API key against a compatible provider's base URL.

    Mirrors the original Next.js /api/provider-nodes/validate endpoint.
    """
    if not body.baseUrl or not body.apiKey:
        return ProviderNodeValidateResponse(valid=False, error="Base URL and API key required")

    # Validate URL format (matching original)
    try:
        parsed = urlparse(body.baseUrl)
        if not parsed.scheme or not parsed.netloc:
            return ProviderNodeValidateResponse(valid=False, error="Invalid URL format")
    except Exception:
        return ProviderNodeValidateResponse(valid=False, error="Invalid URL format")

    node_type = body.type or "openai-compatible"
    handler = _build_node_handler(node_type, body.baseUrl)

    async def _chat_fallback() -> ProviderNodeValidateResponse:
        """Fallback: validate via chat/completions using handler's auth headers."""
        start = time.monotonic()
        url = f"{handler.config.BASE_URL}/chat/completions"
        headers = handler.build_headers(body.apiKey)
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    url, headers=headers,
                    json={"model": body.modelId, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
                )
                if resp.is_success:
                    return ProviderNodeValidateResponse(valid=True, method="chat")
                error = f"Chat request failed ({resp.status_code})"
                try:
                    err_data = resp.json()
                    error = err_data.get("error", {}).get("message", error)
                except Exception:
                    pass
                return ProviderNodeValidateResponse(valid=False, error=error, method="chat")
            except httpx.ConnectError:
                return ProviderNodeValidateResponse(valid=False, error="Connection refused")
            except httpx.TimeoutException:
                return ProviderNodeValidateResponse(valid=False, error="Request timeout")

    # ── Custom Embedding ──
    if node_type == "custom-embedding":
        if not body.modelId:
            return ProviderNodeValidateResponse(
                valid=False, error="Model ID required for embedding validation"
            )
        result = await handler._validate_embedding(body.apiKey, handler.config.BASE_URL, body.modelId)
        return ProviderNodeValidateResponse(
            valid=result.valid, error=result.error,
            method=result.method, dimensions=result.dimensions,
        )

    # ── Anthropic Compatible ──
    if node_type == "anthropic-compatible":
        result = await handler._validate_anthropic_compatible(body.apiKey, handler.config.BASE_URL)
        if result.valid:
            return ProviderNodeValidateResponse(valid=True)
        if body.modelId:
            return await _chat_fallback()
        return ProviderNodeValidateResponse(valid=False, error=result.error)

    # ── OpenAI Compatible (default) ──
    result = await handler._validate_openai_compatible(body.apiKey, handler.config.BASE_URL)
    if result.valid:
        return ProviderNodeValidateResponse(valid=True)
    if body.modelId:
        return await _chat_fallback()
    return ProviderNodeValidateResponse(valid=False, error=result.error)
