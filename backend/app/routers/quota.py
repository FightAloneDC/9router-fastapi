"""Quota tracking endpoints for provider API usage limits."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.provider import ProviderConnection
from app.routers.auth import get_current_user

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
