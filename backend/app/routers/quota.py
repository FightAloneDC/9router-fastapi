"""Quota tracking endpoints for provider API usage limits."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.routers.auth import get_current_user
from app.services.quota import (
    UsageResponse,
    get_usage_handler,
    supported_providers,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quota"])


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
    """List all provider connections with their quota info.

    For now, returns empty quotas as a placeholder for future
    provider API integration that will fetch real usage data.
    """
    result = await db.execute(
        select(ProviderConnection).order_by(
            ProviderConnection.provider, ProviderConnection.priority
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
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Fetch real-time quota/usage data for a connection.

    Calls the provider's usage API using the stored
    access token. Returns standardized quota data.
    """
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

    return await handler.fetch(
        access_token=access_token,
        provider_data=data,
    )


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
