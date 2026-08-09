"""Quota tracking endpoints for provider API usage limits."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.models.quota_cache import QuotaCache
from app.routers.auth import get_current_user
from app.services.quota import (
    QuotaItem as ServiceQuotaItem,
    UsageResponse,
    get_usage_handler,
    supported_providers,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quota"])

# A connection counts as "in use" when it served a proxied
# request within this window (lastUsedAt in the data blob).
IN_USE_WINDOW_S = 60 * 60
# Connections in use re-poll upstream at most this often;
# idle connections are never re-polled automatically.
CACHE_MIN_AGE_S = 15 * 60


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError, AttributeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _quota_cache_usable(
    cache: QuotaCache, data: dict,
) -> bool:
    """Decide whether the cached balance can be served without
    an upstream call.

    Upstream quota polling is limited to reduce ban risk on
    farmed accounts: a cached balance is reused unless it is
    stale AND the connection is in active use.
    """
    fetched_at = cache.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age = (now - fetched_at).total_seconds()
    if age < CACHE_MIN_AGE_S:
        return True
    # Stale cache — only re-poll for connections in active use
    used_at = _parse_iso(data.get("lastUsedAt", ""))
    if used_at is None:
        return True
    return (now - used_at).total_seconds() > IN_USE_WINDOW_S


# --- Schemas ---


class QuotaItem(BaseModel):
    """A single quota metric for a provider connection."""

    name: str
    used: int
    total: int
    reset_at: Optional[str] = None
    remaining_percentage: float


class ProviderQuota(BaseModel):
    """Quota information for a single provider connection."""

    id: str
    provider: str
    name: Optional[str] = None
    is_active: bool
    quotas: list[QuotaItem] = []
    plan: Optional[str] = None


# --- Endpoints ---


@router.get("/quota", response_model=list[ProviderQuota])
async def get_quota(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List connections of providers that support quota
    tracking, each with empty quotas (real usage data is
    fetched per connection via /usage/{connection_id}).
    """
    result = await db.execute(
        select(ProviderConnection)
        .where(
            ProviderConnection.provider.in_(
                supported_providers()
            )
        )
        .order_by(
            ProviderConnection.provider,
            ProviderConnection.priority,
        )
    )
    connections = result.scalars().all()

    return [
        ProviderQuota(
            id=str(conn.id),
            provider=conn.provider,
            name=conn.name,
            is_active=conn.is_active,
            quotas=[],
            plan=None,
        )
        for conn in connections
    ]


@router.get(
    "/usage/{connection_id}",
    response_model=UsageResponse,
)
async def get_connection_usage(
    connection_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Fetch quota/usage data for a connection.

    Serves the cached balance from the quota_cache table when
    possible; calls the provider's usage API only for connections
    without a cache or in active use (ban-risk reduction).
    Pass force=true to always poll upstream.
    """
    # Reject non-UUID ids early — otherwise asyncpg raises a 500 on
    # the bind (e.g. stray "/usage/stream" hitting this param route).
    try:
        uuid.UUID(connection_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=404,
            detail="Connection not found",
        )

    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.id == connection_id
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=404,
            detail="Connection not found",
        )

    handler = get_usage_handler(conn.provider)
    if not handler:
        return UsageResponse(
            message=(
                f"Usage tracking not supported "
                f"for '{conn.provider}'. "
                f"Supported: {', '.join(supported_providers())}"
            )
        )

    # Extract access token from connection data
    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    # Serve cached balance unless a fresh poll is required.
    # Local-state handlers (USES_UPSTREAM=False) are cheap and
    # must reflect current connection state, so they skip cache.
    if not force and handler.USES_UPSTREAM:
        cache = await db.get(QuotaCache, conn.id)
        if cache is not None and _quota_cache_usable(cache, data):
            try:
                cached_quotas = json.loads(cache.quotas or "[]")
            except (json.JSONDecodeError, TypeError):
                cached_quotas = []
            return UsageResponse(
                plan=cache.plan,
                quotas=[
                    ServiceQuotaItem(**q)
                    for q in cached_quotas
                    if isinstance(q, dict)
                ],
                limit_reached=bool(cache.limit_reached),
            )

    access_token = ""
    if handler.USES_UPSTREAM:
        access_token = (
            data.get("accessToken")
            or data.get("apiKey")
            or ""
        )
        if not access_token:
            return UsageResponse(
                message="No access token or API key found"
            )

        # Try to refresh expired OAuth tokens
        if conn.auth_type == "oauth":
            access_token = await _try_refresh_token(
                conn, data, db
            )

    result = await handler.fetch(
        access_token=access_token,
        provider_data=data,
        connection_id=str(conn.id),
    )
    if result.quotas and handler.USES_UPSTREAM:
        await _store_quota_cache(db, conn, result)
    return result


async def _store_quota_cache(
    db: AsyncSession,
    conn: ProviderConnection,
    result: UsageResponse,
) -> None:
    """Persist fetched quota into the quota_cache table.

    Upserts the row keyed by connection id.
    """
    quotas_json = json.dumps(
        [q.model_dump() for q in result.quotas]
    )
    cache = await db.get(QuotaCache, conn.id)
    if cache is None:
        cache = QuotaCache(connection_id=conn.id)
        db.add(cache)
    cache.plan = result.plan
    cache.quotas = quotas_json
    cache.limit_reached = result.limit_reached
    cache.fetched_at = datetime.now(timezone.utc)
    await db.commit()


async def _try_refresh_token(
    conn: ProviderConnection,
    data: dict,
    db: AsyncSession,
) -> str:
    """Attempt to refresh an expired OAuth token.

    Returns the (possibly refreshed) access token.
    Falls back to the existing token on failure.
    """
    from datetime import datetime, timezone

    expires_at_str = data.get("expiresAt", "")
    refresh_token = data.get("refreshToken", "")

    if not expires_at_str or not refresh_token:
        return data.get("accessToken", "")

    try:
        expires_at = datetime.fromisoformat(
            expires_at_str.replace("Z", "+00:00")
        )
        if expires_at.tzinfo is None:
            from datetime import timezone as tz
            expires_at = expires_at.replace(tzinfo=tz.utc)
    except (ValueError, TypeError):
        return data.get("accessToken", "")

    now = datetime.now(timezone.utc)
    if expires_at > now:
        return data.get("accessToken", "")

    # Token expired — try refresh
    try:
        from app.services.oauth import refresh_access_token

        result = await refresh_access_token(
            conn.provider, refresh_token
        )
        new_token = result.get("access_token", "")
        if new_token:
            # Persist refreshed token
            data["accessToken"] = new_token
            if result.get("refresh_token"):
                data["refreshToken"] = result[
                    "refresh_token"
                ]
            if result.get("expires_at"):
                data["expiresAt"] = result["expires_at"]
            conn.data = json.dumps(data)
            await db.commit()
            return new_token
    except Exception as e:
        logger.warning(
            "Token refresh failed for %s (%s): %s",
            conn.id, conn.provider, e,
        )

    return data.get("accessToken", "")
