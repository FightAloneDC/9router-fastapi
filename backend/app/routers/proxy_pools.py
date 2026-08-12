"""Proxy pool management endpoints."""

import json
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.models.proxy_pool import ProxyPool
from app.routers.auth import get_current_user
from app.schemas.proxy_pool import (
    ProxyPoolCreate,
    ProxyPoolOut,
    ProxyPoolTestResult,
    ProxyPoolUpdate,
)
from app.services.outbound_proxy import merge_proxy_usage_into_data

router = APIRouter(prefix="/proxy-pools", tags=["proxy-pools"])


async def apply_pool_usage_to_connections(
    db: AsyncSession,
    pool: ProxyPool,
) -> int:
    """Apply the pool's usage template to every assigned connection."""
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.proxy_pool_id == pool.id
        )
    )
    connections = result.scalars().all()

    for connection in connections:
        data = json.loads(connection.data) if connection.data else {}
        connection.data = json.dumps(
            merge_proxy_usage_into_data(data, pool.default_proxy_usage)
        )

    return len(connections)


@router.get("", response_model=list[ProxyPoolOut])
async def list_proxy_pools(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all proxy pools."""
    result = await db.execute(select(ProxyPool).order_by(ProxyPool.created_at.desc()))
    pools = result.scalars().all()
    return [ProxyPoolOut.model_validate(p) for p in pools]


@router.post(
    "",
    response_model=ProxyPoolOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_proxy_pool(
    body: ProxyPoolCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Create a new proxy pool."""
    pool = ProxyPool(
        name=body.name,
        proxy_url=body.proxy_url,
        no_proxy=body.no_proxy,
        pool_type=body.pool_type,
        is_active=body.is_active,
        strict_proxy=body.strict_proxy,
        default_proxy_usage=body.default_proxy_usage,
    )
    db.add(pool)
    await db.flush()
    await db.refresh(pool)
    return ProxyPoolOut.model_validate(pool)


@router.post("/{pool_id}/apply-usage")
async def apply_proxy_pool_usage(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Apply the pool's usage template to assigned connections."""
    result = await db.execute(select(ProxyPool).where(ProxyPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy pool not found",
        )

    updated = await apply_pool_usage_to_connections(db, pool)
    await db.commit()
    return {"updated": updated}


@router.get("/{pool_id}", response_model=ProxyPoolOut)
async def get_proxy_pool(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get a single proxy pool by ID."""
    result = await db.execute(select(ProxyPool).where(ProxyPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy pool not found",
        )
    return ProxyPoolOut.model_validate(pool)


@router.patch("/{pool_id}", response_model=ProxyPoolOut)
async def update_proxy_pool(
    pool_id: str,
    body: ProxyPoolUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update a proxy pool."""
    result = await db.execute(select(ProxyPool).where(ProxyPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy pool not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pool, field, value)

    await db.flush()
    await db.refresh(pool)
    return ProxyPoolOut.model_validate(pool)


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_proxy_pool(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a proxy pool."""
    result = await db.execute(select(ProxyPool).where(ProxyPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy pool not found",
        )
    await db.delete(pool)


@router.post("/{pool_id}/test", response_model=ProxyPoolTestResult)
async def test_proxy_pool(
    pool_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Test proxy connectivity by making an HTTP HEAD request through the proxy."""
    result = await db.execute(select(ProxyPool).where(ProxyPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proxy pool not found",
        )

    test_url = "https://httpbin.org/ip"
    start = time.monotonic()
    error_msg = None
    test_status = "active"
    latency = None

    try:
        async with httpx.AsyncClient(
            proxy=pool.proxy_url,
            timeout=15.0,
        ) as client:
            resp = await client.head(test_url)
            latency = (time.monotonic() - start) * 1000
            if resp.status_code >= 400:
                test_status = "error"
                error_msg = f"HTTP {resp.status_code}"
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        test_status = "error"
        error_msg = str(exc)[:500]

    # Update the pool's test metadata
    pool.test_status = test_status
    pool.last_tested_at = datetime.now(timezone.utc)
    pool.last_error = error_msg
    await db.flush()
    await db.refresh(pool)

    return ProxyPoolTestResult(
        id=pool.id,
        status=test_status,
        latency_ms=round(latency, 2) if latency else None,
        error=error_msg,
    )
