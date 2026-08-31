"""Morph usage handler — local monthly free-request bar.

Morph publishes exactly one numeric cap: 200 requests per month on
the free tier (https://www.morphllm.com/pricing, retrieved
2026-08-18). No RPM / TPM / TPD table exists anywhere in the docs,
so this handler exposes a single local bar: this connection's
``usage_history`` requests since UTC month start vs the 200 cap.
Paid/payg plans publish no request cap and get no bar.

No x-ratelimit overlay: Morph documents no ``x-ratelimit-*``
headers. No usage-API poll: no usage/credits API is documented.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app import database
from app.models.usage import UsageHistory
from app.providers.morph.config import MorphConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_BAR_NAME = "Morph monthly free requests"
_PRICING_SOURCE = (
    "https://www.morphllm.com/pricing (retrieved 2026-08-18)"
)


def _plan(account_type: str | None) -> str:
    plan = (account_type or "free").strip().lower()
    if plan in ("subscribe", "scale", "tokenplan"):
        return "subscribe"
    if plan in ("payg", "paid"):
        return "payg"
    return "free"


def _monthly_cap() -> int:
    """Free-tier monthly request cap from RATE_LIMITS."""
    table = MorphConfig().RATE_LIMITS
    return int(table.get("free", {}).get("calls") or 200)


def _month_start_utc(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _next_month_start_iso(now: datetime) -> str:
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return nxt.isoformat()


def monthly_bar(used: int, *, reset_at: str | None) -> dict:
    """One free-tier monthly requests bar (dict shape)."""
    total = _monthly_cap()
    remaining = max(0, total - used)
    pct = 100.0 if total <= 0 else max(
        0.0, remaining / total * 100,
    )
    return {
        "name": _BAR_NAME,
        "used": min(used, total) if total else used,
        "total": total,
        "remaining": remaining,
        "remaining_percentage": pct,
        "reset_at": reset_at,
        "unlimited": False,
    }


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


async def count_requests_since(
    since: datetime,
    connection_id: str | None,
) -> int:
    """Count this connection's morph requests in usage_history."""
    cid = _cid_key(connection_id)
    async with database.async_session() as db:
        cond = [
            func.lower(UsageHistory.provider) == "morph",
            UsageHistory.timestamp >= since,
        ]
        if cid:
            stored = func.replace(
                func.lower(
                    func.coalesce(UsageHistory.connection_id, ""),
                ),
                "-",
                "",
            )
            cond.append(stored == cid)
        result = await db.execute(
            select(func.count()).select_from(
                UsageHistory,
            ).where(*cond)
        )
        return int(result.scalar() or 0)


class MorphUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "morph"
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del access_token
        data = provider_data or {}
        plan = _plan(str(data.get("accountType") or "free"))
        if plan != "free":
            return UsageResponse(
                plan=plan,
                message=(
                    "Morph PAYG and Scale publish no numeric "
                    "request cap (practically no rate limits)."
                ),
            )
        now = datetime.now(timezone.utc)
        used = await count_requests_since(
            _month_start_utc(now), connection_id,
        )
        bar = monthly_bar(
            used, reset_at=_next_month_start_iso(now),
        )
        return UsageResponse(
            plan=plan,
            quotas=[QuotaItem(**bar)],
            limit_reached=used >= _monthly_cap(),
            message=(
                "Morph free tier: 200 requests per month "
                f"({_PRICING_SOURCE}). Used counts this "
                "connection's local usage since UTC month start."
            ),
        )
