"""Quota tracking endpoints for provider API usage limits."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.models.quota_cache import QuotaCache
from app.routers.auth import get_current_user
from app.services.proxy import invalidate_connection_cache
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
    supports_quota_details: bool = False


class QuotaListResponse(BaseModel):
    """Paginated quota tracker payload."""

    items: list[ProviderQuota]
    total: int
    page: int
    page_size: int
    provider_types: list[str]
    stats: dict


# --- Helpers ---


def _parse_cached_quotas(raw: str | None) -> list[QuotaItem]:
    try:
        data = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []
    items: list[QuotaItem] = []
    for q in data:
        if not isinstance(q, dict) or "name" not in q:
            continue
        try:
            items.append(
                QuotaItem(
                    name=str(q.get("name") or ""),
                    used=int(q.get("used") or 0),
                    total=int(q.get("total") or 0),
                    reset_at=q.get("reset_at"),
                    remaining_percentage=float(
                        q.get("remaining_percentage") or 0
                    ),
                )
            )
        except (TypeError, ValueError):
            continue
    return items


def _min_remaining(quotas: list[QuotaItem]) -> float:
    if not quotas:
        return 100.0
    return min(q.remaining_percentage for q in quotas)


def _earliest_reset_ms(quotas: list[QuotaItem]) -> float:
    times: list[float] = []
    for q in quotas:
        if not q.reset_at:
            continue
        dt = _parse_iso(q.reset_at)
        if dt is not None:
            times.append(dt.timestamp() * 1000)
    return min(times) if times else float("inf")


# --- Endpoints ---


@router.get("/quota", response_model=QuotaListResponse)
async def get_quota(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider: str | None = Query(
        None, description="Filter by provider id"
    ),
    status: str | None = Query(
        None, description="active | inactive"
    ),
    search: str | None = Query(
        None, description="Match connection name"
    ),
    sort: str | None = Query(
        None,
        description="remaining-asc | remaining-desc",
    ),
    expiring_first: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Paginated connections for the quota tracker.

    Quotas come from quota_cache (no upstream poll). Call
    GET /usage/{id}?force=true to refresh one connection.
    """
    supported = supported_providers()
    stmt = (
        select(ProviderConnection, QuotaCache)
        .outerjoin(
            QuotaCache,
            QuotaCache.connection_id == ProviderConnection.id,
        )
        .where(ProviderConnection.provider.in_(supported))
    )
    if provider:
        stmt = stmt.where(ProviderConnection.provider == provider)
    if status == "active":
        stmt = stmt.where(ProviderConnection.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(ProviderConnection.is_active.is_(False))
    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(ProviderConnection.name.ilike(q))

    stmt = stmt.order_by(
        ProviderConnection.provider,
        ProviderConnection.priority,
        ProviderConnection.id,
    )
    rows = (await db.execute(stmt)).all()

    # Distinct providers (unfiltered by provider/status/search
    # except supported set) for the filter dropdown.
    types_result = await db.execute(
        select(ProviderConnection.provider)
        .where(ProviderConnection.provider.in_(supported))
        .distinct()
        .order_by(ProviderConnection.provider)
    )
    provider_types = [r[0] for r in types_result.all()]

    enriched: list[tuple[ProviderConnection, list[QuotaItem], str | None]] = []
    active_with_limits = 0
    low_quotas = 0
    for conn, cache in rows:
        quotas = _parse_cached_quotas(
            cache.quotas if cache else None
        )
        plan = cache.plan if cache else None
        if conn.is_active and quotas:
            active_with_limits += 1
        low_quotas += sum(
            1 for q in quotas if q.remaining_percentage <= 30
        )
        enriched.append((conn, quotas, plan))

    if sort == "remaining-asc":
        enriched.sort(key=lambda x: _min_remaining(x[1]))
    elif sort == "remaining-desc":
        enriched.sort(
            key=lambda x: _min_remaining(x[1]), reverse=True
        )
    if expiring_first:
        enriched.sort(key=lambda x: _earliest_reset_ms(x[1]))

    total = len(enriched)
    start = (page - 1) * page_size
    page_rows = enriched[start:start + page_size]

    items: list[ProviderQuota] = []
    for conn, quotas, plan in page_rows:
        handler = get_usage_handler(conn.provider)
        supports_details = (
            handler is not None
            and hasattr(handler, "fetch_model_details")
        )
        # Local-state handlers (grok-cli, …) are cheap DB sums —
        # refresh the visible page so the list is not stuck on
        # stale header snapshots (used always 0).
        if handler is not None and not handler.USES_UPSTREAM:
            try:
                data = (
                    json.loads(conn.data) if conn.data else {}
                )
            except (json.JSONDecodeError, TypeError):
                data = {}
            try:
                cred = (
                    data.get("accessToken")
                    or data.get("apiKey")
                    or ""
                )
                result = await handler.fetch(
                    access_token=cred,
                    provider_data=data,
                    connection_id=str(conn.id),
                )
                if result.quotas:
                    await _store_quota_cache(db, conn, result)
                    quotas = [
                        QuotaItem(
                            name=q.name,
                            used=q.used,
                            total=q.total,
                            reset_at=q.reset_at,
                            remaining_percentage=(
                                q.remaining_percentage
                            ),
                        )
                        for q in result.quotas
                    ]
                    if result.plan:
                        plan = result.plan
            except Exception as e:
                logger.warning(
                    "Local quota refresh failed for %s: %s",
                    conn.id,
                    e,
                )
        items.append(
            ProviderQuota(
                id=str(conn.id),
                provider=conn.provider,
                name=conn.name,
                is_active=conn.is_active,
                quotas=quotas,
                plan=plan,
                supports_quota_details=supports_details,
            )
        )

    return QuotaListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        provider_types=provider_types,
        stats={
            "total": total,
            "active_with_limits": active_with_limits,
            "low_quotas": low_quotas,
        },
    )


@router.post("/quota/bulk-disable-depleted")
async def bulk_disable_depleted(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Disable active connections whose cached quota is ≤ 5%."""
    supported = supported_providers()
    rows = (
        await db.execute(
            select(ProviderConnection, QuotaCache)
            .outerjoin(
                QuotaCache,
                QuotaCache.connection_id
                == ProviderConnection.id,
            )
            .where(
                ProviderConnection.provider.in_(supported),
                ProviderConnection.is_active.is_(True),
            )
        )
    ).all()

    updated = 0
    for conn, cache in rows:
        quotas = _parse_cached_quotas(
            cache.quotas if cache else None
        )
        if any(q.remaining_percentage <= 5 for q in quotas):
            conn.is_active = False
            invalidate_connection_cache(str(conn.id))
            updated += 1

    await db.commit()
    return {"updated": updated}


@router.post("/quota/bulk-enable-inactive")
async def bulk_enable_inactive(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Re-enable all inactive quota-tracked connections."""
    supported = supported_providers()
    result = await db.execute(
        select(ProviderConnection).where(
            ProviderConnection.provider.in_(supported),
            ProviderConnection.is_active.is_(False),
        )
    )
    connections = result.scalars().all()
    for conn in connections:
        conn.is_active = True
        invalidate_connection_cache(str(conn.id))
    await db.commit()
    return {"updated": len(connections)}


@router.get(
    "/usage/{connection_id}",
    response_model=UsageResponse,
)
async def get_connection_usage(
    connection_id: str,
    force: bool = False,
    detail: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Fetch quota/usage data for a connection.

    Serves the cached balance from the quota_cache table when
    possible; calls the provider's usage API only for connections
    without a cache or in active use (ban-risk reduction).
    Pass force=true to always poll upstream.

    Pass detail=models for providers that support a full per-model
    breakdown (e.g. alims-intl). That payload is not cached.
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

    want_models = (detail or "").strip().lower() == "models"
    if want_models:
        detail_fn = getattr(handler, "fetch_model_details", None)
        if detail_fn is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Per-model quota detail is not supported "
                    f"for '{conn.provider}'."
                ),
            )
        return await detail_fn(
            access_token="",
            provider_data=data,
            connection_id=str(conn.id),
        )

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

    access_token = (
        data.get("accessToken")
        or data.get("apiKey")
        or ""
    )
    if handler.USES_UPSTREAM:
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
    # Persist for all handlers (including local-state like grok-cli)
    # so GET /quota list stays accurate after refresh.
    if result.quotas:
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
