"""Provider Node CRUD and validation endpoints."""

import json
import uuid as _uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection, ProviderNode
from app.routers.auth import get_current_user
from app.routers.providers._router import router
from app.routers.providers.helpers import _get_chat_error_message, _get_models_error_message, _node_to_out
from app.schemas.provider import (
    ProviderNodeCreate,
    ProviderNodeOut,
    ProviderNodeUpdate,
    ProviderNodeValidateRequest,
    ProviderNodeValidateResponse,
)


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
        conn.data = json.dumps(conn_data)

    await db.flush()
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
        from urllib.parse import urlparse
        parsed = urlparse(body.baseUrl)
        if not parsed.scheme or not parsed.netloc:
            return ProviderNodeValidateResponse(valid=False, error="Invalid URL format")
    except Exception:
        return ProviderNodeValidateResponse(valid=False, error="Invalid URL format")

    timeout = 10.0
    async with httpx.AsyncClient(timeout=timeout) as client:
        # ── Custom Embedding ──
        if body.type == "custom-embedding":
            if not body.modelId:
                return ProviderNodeValidateResponse(
                    valid=False, error="Model ID required for embedding validation"
                )
            normalized = body.baseUrl.rstrip("/")
            try:
                resp = await client.post(
                    f"{normalized}/embeddings",
                    headers={
                        "Authorization": f"Bearer {body.apiKey}",
                        "Content-Type": "application/json",
                    },
                    json={"model": body.modelId, "input": "ping"},
                )
                if resp.is_success:
                    data = resp.json()
                    dims = None
                    if isinstance(data, dict):
                        emb = data.get("data", [{}])
                        if emb and isinstance(emb[0].get("embedding"), list):
                            dims = len(emb[0]["embedding"])
                    return ProviderNodeValidateResponse(
                        valid=True, method="embeddings", dimensions=dims
                    )
                if resp.status_code in (401, 403):
                    return ProviderNodeValidateResponse(valid=False, error="API key unauthorized")
                return ProviderNodeValidateResponse(
                    valid=False,
                    error=f"Embeddings request failed ({resp.status_code})",
                    method="embeddings",
                )
            except httpx.ConnectError:
                return ProviderNodeValidateResponse(valid=False, error="Connection refused")
            except httpx.TimeoutException:
                return ProviderNodeValidateResponse(valid=False, error="Request timeout (>10s)")

        # ── Anthropic Compatible ──
        if body.type == "anthropic-compatible":
            normalized = body.baseUrl.rstrip("/")
            if normalized.endswith("/messages"):
                normalized = normalized[:-9]
            try:
                resp = await client.get(
                    f"{normalized}/models",
                    headers={
                        "x-api-key": body.apiKey,
                        "anthropic-version": "2023-06-01",
                        "Authorization": f"Bearer {body.apiKey}",
                    },
                )
                if resp.is_success:
                    return ProviderNodeValidateResponse(valid=True)
                if resp.status_code in (401, 403):
                    return ProviderNodeValidateResponse(valid=False, error="API key unauthorized")
                # Fallback: chat/completions if modelId provided
                if body.modelId:
                    chat_resp = await client.post(
                        f"{normalized}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {body.apiKey}",
                            "Content-Type": "application/json",
                            "x-api-key": body.apiKey,
                            "anthropic-version": "2023-06-01",
                        },
                        json={
                            "model": body.modelId,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                        },
                    )
                    if chat_resp.is_success:
                        return ProviderNodeValidateResponse(valid=True, method="chat")
                    return ProviderNodeValidateResponse(
                        valid=False,
                        error=_get_chat_error_message(chat_resp.status_code),
                        method="chat",
                    )
                return ProviderNodeValidateResponse(
                    valid=False, error=_get_models_error_message(resp.status_code)
                )
            except httpx.ConnectError:
                return ProviderNodeValidateResponse(valid=False, error="Connection refused")
            except httpx.TimeoutException:
                return ProviderNodeValidateResponse(valid=False, error="Request timeout (>10s)")

        # ── OpenAI Compatible (default) ──
        normalized = body.baseUrl.rstrip("/")
        try:
            resp = await client.get(
                f"{normalized}/models",
                headers={"Authorization": f"Bearer {body.apiKey}"},
            )
            if resp.is_success:
                return ProviderNodeValidateResponse(valid=True)
            if resp.status_code in (401, 403):
                return ProviderNodeValidateResponse(valid=False, error="API key unauthorized")
            # Fallback: chat/completions if modelId provided
            if body.modelId:
                chat_resp = await client.post(
                    f"{normalized}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {body.apiKey}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": body.modelId,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    },
                )
                if chat_resp.is_success:
                    return ProviderNodeValidateResponse(valid=True, method="chat")
                return ProviderNodeValidateResponse(
                    valid=False,
                    error=_get_chat_error_message(chat_resp.status_code),
                    method="chat",
                )
            return ProviderNodeValidateResponse(
                valid=False, error=_get_models_error_message(resp.status_code)
            )
        except httpx.ConnectError:
            return ProviderNodeValidateResponse(valid=False, error="Connection refused")
        except httpx.TimeoutException:
            return ProviderNodeValidateResponse(valid=False, error="Request timeout (>10s)")
        except Exception as e:
            return ProviderNodeValidateResponse(
                valid=False, error=f"Network connection failed: {str(e)[:200]}"
            )
