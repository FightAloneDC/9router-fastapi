"""Usage analytics endpoints."""

import json
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.models.request_detail import RequestDetail
from app.models.usage import UsageHistory
from app.routers.auth import get_current_user
from app.schemas.usage import (
    PaginationInfo,
    RecentRequestItem,
    RequestDetailOut,
    TopApiKeyItem,
    UsageAccountItem,
    UsageApiKeyItem,
    UsageChartPoint,
    UsageEndpointItem,
    UsageHistoryOut,
    UsageModelItem,
    UsageProviderItem,
    UsageRequestDetailsOut,
    UsageStatsOut,
)

router = APIRouter(prefix="/usage", tags=["usage"])


def _parse_period(period: str) -> datetime:
    """Return the start datetime for a given period string."""
    now = datetime.now(timezone.utc)
    mapping = {
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "60d": now - timedelta(days=60),
        "90d": now - timedelta(days=90),
        "all": datetime(2020, 1, 1, tzinfo=timezone.utc),
    }
    return mapping.get(period, now - timedelta(days=7))


def _safe_json_parse(raw: str | None) -> dict:
    """Safely parse a JSON string, returning {} on failure."""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


@router.get("/stats", response_model=UsageStatsOut)
async def get_usage_stats(
    period: str = Query("7d", pattern="^(today|24h|7d|30d|60d|90d|all)$"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return aggregated usage statistics for the requested period."""
    since = _parse_period(period)

    # Total counts
    count_result = await db.execute(
        select(
            func.count(UsageHistory.id).label("total_requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "total_prompt"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "total_completion"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("total_cost"),
        ).where(UsageHistory.timestamp >= since)
    )
    row = count_result.one()

    # By provider
    provider_result = await db.execute(
        select(
            UsageHistory.provider,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "prompt_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
        )
        .where(UsageHistory.timestamp >= since)
        .group_by(UsageHistory.provider)
        .order_by(func.count(UsageHistory.id).desc())
    )
    by_provider = [
        UsageProviderItem(
            name=r.provider or "unknown",
            requests=r.requests,
            promptTokens=r.prompt_tokens,
            completionTokens=r.completion_tokens,
            cost=float(r.cost),
        )
        for r in provider_result.all()
    ]

    # By model
    model_result = await db.execute(
        select(
            UsageHistory.model,
            UsageHistory.provider,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "prompt_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
            func.max(UsageHistory.timestamp).label("last_used"),
        )
        .where(UsageHistory.timestamp >= since)
        .group_by(UsageHistory.model, UsageHistory.provider)
        .order_by(func.count(UsageHistory.id).desc())
    )
    by_model = [
        UsageModelItem(
            name=r.model or "unknown",
            provider=r.provider or "unknown",
            requests=r.requests,
            promptTokens=r.prompt_tokens,
            completionTokens=r.completion_tokens,
            cost=float(r.cost),
            lastUsed=r.last_used.isoformat() if r.last_used else None,
        )
        for r in model_result.all()
    ]

    # By account (connection_id) — join with provider_connections for display name
    account_result = await db.execute(
        select(
            UsageHistory.connection_id,
            UsageHistory.model,
            UsageHistory.provider,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "prompt_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
            func.max(UsageHistory.timestamp).label("last_used"),
            ProviderConnection.name.label("account_name"),
        )
        .outerjoin(
            ProviderConnection,
            UsageHistory.connection_id == func.cast(ProviderConnection.id, String),
        )
        .where(UsageHistory.timestamp >= since)
        .where(UsageHistory.connection_id.isnot(None))
        .group_by(UsageHistory.connection_id, UsageHistory.model, UsageHistory.provider, ProviderConnection.name)
        .order_by(func.count(UsageHistory.id).desc())
    )
    by_account = [
        UsageAccountItem(
            connectionId=r.connection_id or "",
            accountName=r.account_name or r.connection_id or "unknown",
            rawModel=r.model or "unknown",
            provider=r.provider or "unknown",
            requests=r.requests,
            promptTokens=r.prompt_tokens,
            completionTokens=r.completion_tokens,
            cost=float(r.cost),
            lastUsed=r.last_used.isoformat() if r.last_used else None,
        )
        for r in account_result.all()
    ]

    # By API key
    apikey_result = await db.execute(
        select(
            UsageHistory.api_key,
            UsageHistory.model,
            UsageHistory.provider,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "prompt_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
            func.max(UsageHistory.timestamp).label("last_used"),
        )
        .where(UsageHistory.timestamp >= since)
        .where(UsageHistory.api_key.isnot(None))
        .group_by(UsageHistory.api_key, UsageHistory.model, UsageHistory.provider)
        .order_by(func.count(UsageHistory.id).desc())
    )
    by_apikey = [
        UsageApiKeyItem(
            keyName=r.api_key or "unknown",
            rawModel=r.model or "unknown",
            provider=r.provider or "unknown",
            requests=r.requests,
            promptTokens=r.prompt_tokens,
            completionTokens=r.completion_tokens,
            cost=float(r.cost),
            lastUsed=r.last_used.isoformat() if r.last_used else None,
        )
        for r in apikey_result.all()
    ]

    # By endpoint
    endpoint_result = await db.execute(
        select(
            UsageHistory.endpoint,
            UsageHistory.model,
            UsageHistory.provider,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "prompt_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "completion_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
            func.max(UsageHistory.timestamp).label("last_used"),
        )
        .where(UsageHistory.timestamp >= since)
        .where(UsageHistory.endpoint.isnot(None))
        .group_by(UsageHistory.endpoint, UsageHistory.model, UsageHistory.provider)
        .order_by(func.count(UsageHistory.id).desc())
    )
    by_endpoint = [
        UsageEndpointItem(
            endpoint=r.endpoint or "unknown",
            rawModel=r.model or "unknown",
            provider=r.provider or "unknown",
            requests=r.requests,
            promptTokens=r.prompt_tokens,
            completionTokens=r.completion_tokens,
            cost=float(r.cost),
            lastUsed=r.last_used.isoformat() if r.last_used else None,
        )
        for r in endpoint_result.all()
    ]

    # Top API keys (aggregated across all models, sorted by cost desc, limit 10)
    top_apikey_result = await db.execute(
        select(
            UsageHistory.api_key,
            func.count(UsageHistory.id).label("requests"),
            func.coalesce(func.sum(UsageHistory.prompt_tokens), 0).label(
                "input_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.completion_tokens), 0).label(
                "output_tokens"
            ),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
        )
        .where(UsageHistory.timestamp >= since)
        .where(UsageHistory.api_key.isnot(None))
        .group_by(UsageHistory.api_key)
        .order_by(func.sum(UsageHistory.cost).desc())
        .limit(10)
    )
    top_apikeys = [
        TopApiKeyItem(
            keyName=r.api_key or "unknown",
            cost=float(r.cost),
            requests=r.requests,
            inputTokens=r.input_tokens,
            outputTokens=r.output_tokens,
            cacheCreationTokens=0,
            cacheReadTokens=0,
            totalTokens=r.input_tokens + r.output_tokens,
            totalCost=float(r.cost),
        )
        for r in top_apikey_result.all()
    ]

    # Cost change: compare current period with prior period of same length
    period_length = datetime.now(timezone.utc) - since
    prior_since = since - period_length
    prior_cost_result = await db.execute(
        select(
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("prior_cost"),
        ).where(UsageHistory.timestamp >= prior_since).where(UsageHistory.timestamp < since)
    )
    prior_cost = float(prior_cost_result.scalar() or 0)
    current_cost = float(row.total_cost)
    cost_change = 0.0
    if prior_cost > 0:
        cost_change = ((current_cost - prior_cost) / prior_cost) * 100
    cost_per_request = current_cost / row.total_requests if row.total_requests > 0 else 0.0

    # Recent requests (last 20)
    recent_result = await db.execute(
        select(
            UsageHistory.timestamp,
            UsageHistory.model,
            UsageHistory.provider,
            UsageHistory.prompt_tokens,
            UsageHistory.completion_tokens,
            UsageHistory.status,
        )
        .where(UsageHistory.timestamp >= since)
        .order_by(UsageHistory.timestamp.desc())
        .limit(20)
    )
    recent_requests = [
        RecentRequestItem(
            timestamp=r.timestamp.isoformat() if r.timestamp else "",
            model=r.model or "unknown",
            provider=r.provider or "unknown",
            promptTokens=r.prompt_tokens or 0,
            completionTokens=r.completion_tokens or 0,
            status=r.status or "ok",
        )
        for r in recent_result.all()
    ]

    return UsageStatsOut(
        totalRequests=row.total_requests,
        totalPromptTokens=row.total_prompt,
        totalCompletionTokens=row.total_completion,
        totalCacheCreationTokens=0,
        totalCacheReadTokens=0,
        totalCost=float(row.total_cost),
        costChange=round(cost_change, 1),
        costPerRequest=round(cost_per_request, 4),
        byProvider=by_provider,
        byModel=by_model,
        byAccount=by_account,
        byApiKey=by_apikey,
        byEndpoint=by_endpoint,
        topApiKeys=top_apikeys,
        recentRequests=recent_requests,
    )


@router.get("/chart", response_model=list[UsageChartPoint])
async def get_usage_chart(
    period: str = Query("7d", pattern="^(today|24h|7d|30d|60d|90d|all)$"),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return chart data points aggregated by day (or hour for 'today')."""
    since = _parse_period(period)

    if period == "today":
        # Aggregate by hour for today (PostgreSQL)
        rows_result = await db.execute(
            select(
                func.to_char(
                    func.date_trunc("hour", UsageHistory.timestamp), "HH24:00"
                ).label("bucket"),
                func.coalesce(
                    func.sum(UsageHistory.prompt_tokens + UsageHistory.completion_tokens),
                    0,
                ).label("tokens"),
                func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
            )
            .where(UsageHistory.timestamp >= since)
            .group_by("bucket")
            .order_by("bucket")
        )
        data = rows_result.all()
        return [
            UsageChartPoint(
                label=r.bucket,
                tokens=r.tokens,
                cost=float(r.cost),
            )
            for r in data
        ]

    # Aggregate by day for multi-day periods (PostgreSQL)
    rows_result = await db.execute(
        select(
            func.to_char(
                func.date_trunc("day", UsageHistory.timestamp), "Mon DD"
            ).label("day_label"),
            func.to_char(
                func.date_trunc("day", UsageHistory.timestamp), "YYYY-MM-DD"
            ).label("day_sort"),
            func.coalesce(
                func.sum(UsageHistory.prompt_tokens + UsageHistory.completion_tokens),
                0,
            ).label("tokens"),
            func.coalesce(func.sum(UsageHistory.cost), 0.0).label("cost"),
        )
        .where(UsageHistory.timestamp >= since)
        .group_by("day_label", "day_sort")
        .order_by("day_sort")
    )
    data = rows_result.all()

    return [
        UsageChartPoint(
            label=r.day_label,
            tokens=r.tokens,
            cost=float(r.cost),
        )
        for r in data
    ]


@router.get("/history", response_model=list[UsageHistoryOut])
async def get_usage_history(
    provider: str | None = Query(None),
    model: str | None = Query(None),
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return raw usage history with optional filters."""
    query = select(UsageHistory).order_by(UsageHistory.timestamp.desc())

    if provider:
        query = query.where(UsageHistory.provider.ilike(f"%{provider}%"))
    if model:
        query = query.where(UsageHistory.model.ilike(f"%{model}%"))
    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate)
            query = query.where(UsageHistory.timestamp >= start_dt)
        except ValueError:
            pass
    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate)
            query = query.where(UsageHistory.timestamp <= end_dt)
        except ValueError:
            pass

    result = await db.execute(query.limit(500))
    rows = result.scalars().all()

    return [
        UsageHistoryOut(
            id=r.id,
            timestamp=r.timestamp,
            provider=r.provider,
            model=r.model,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            cost=r.cost,
            status=r.status,
            tokens=_safe_json_parse(r.tokens),
        )
        for r in rows
    ]


@router.get("/providers")
async def get_usage_providers(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return list of unique provider names from usage history."""
    result = await db.execute(
        select(UsageHistory.provider)
        .where(UsageHistory.provider.isnot(None))
        .distinct()
        .order_by(UsageHistory.provider)
    )
    providers = [{"id": r[0], "name": r[0]} for r in result.all() if r[0]]
    return {"providers": providers}


@router.get("/request-details", response_model=UsageRequestDetailsOut)
async def get_request_details(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    provider: str | None = Query(None),
    model: str | None = Query(None),
    startDate: str | None = Query(None),
    endDate: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return paginated request details from request_details table."""
    # Base query — use RequestDetail so IDs match the detail endpoint
    base_query = select(RequestDetail)
    count_query = select(func.count(RequestDetail.id))

    if provider:
        base_query = base_query.where(RequestDetail.provider.ilike(f"%{provider}%"))
        count_query = count_query.where(RequestDetail.provider.ilike(f"%{provider}%"))
    if model:
        base_query = base_query.where(RequestDetail.model.ilike(f"%{model}%"))
        count_query = count_query.where(RequestDetail.model.ilike(f"%{model}%"))
    if startDate:
        try:
            start_dt = datetime.fromisoformat(startDate)
            base_query = base_query.where(RequestDetail.timestamp >= start_dt)
            count_query = count_query.where(RequestDetail.timestamp >= start_dt)
        except ValueError:
            pass
    if endDate:
        try:
            end_dt = datetime.fromisoformat(endDate)
            base_query = base_query.where(RequestDetail.timestamp <= end_dt)
            count_query = count_query.where(RequestDetail.timestamp <= end_dt)
        except ValueError:
            pass

    # Get total count
    count_result = await db.execute(count_query)
    total_items = count_result.scalar() or 0
    total_pages = max(1, math.ceil(total_items / pageSize))

    # Get paginated results
    offset = (page - 1) * pageSize
    result = await db.execute(
        base_query.order_by(RequestDetail.timestamp.desc())
        .offset(offset)
        .limit(pageSize)
    )
    rows = result.scalars().all()

    # Return list items without the large payload fields
    details = [
        RequestDetailOut(
            id=r.id,
            timestamp=r.timestamp,
            provider=r.provider,
            model=r.model,
            connection_id=r.connection_id,
            status=r.status,
            latency_ttft=r.latency_ttft,
            latency_total=r.latency_total,
            prompt_tokens=r.prompt_tokens or 0,
            completion_tokens=r.completion_tokens or 0,
            cost=r.cost or 0.0,
            # Payload fields omitted in list — fetched on detail click
            request=None,
            provider_request=None,
            provider_response=None,
            response=None,
        )
        for r in rows
    ]

    return UsageRequestDetailsOut(
        details=details,
        pagination=PaginationInfo(
            page=page,
            pageSize=pageSize,
            totalItems=total_items,
            totalPages=total_pages,
        ),
    )


@router.get("/request-detail/{detail_id}", response_model=RequestDetailOut)
async def get_request_detail(
    detail_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Return full request detail with payloads by ID."""
    result = await db.execute(
        select(RequestDetail).where(RequestDetail.id == detail_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Request detail not found")

    def _parse(raw):
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    return RequestDetailOut(
        id=row.id,
        timestamp=row.timestamp,
        provider=row.provider,
        model=row.model,
        connection_id=row.connection_id,
        status=row.status,
        latency_ttft=row.latency_ttft,
        latency_total=row.latency_total,
        prompt_tokens=row.prompt_tokens or 0,
        completion_tokens=row.completion_tokens or 0,
        cost=row.cost or 0.0,
        request=_parse(row.request),
        provider_request=_parse(row.provider_request),
        provider_response=_parse(row.provider_response),
        response=_parse(row.response),
    )
