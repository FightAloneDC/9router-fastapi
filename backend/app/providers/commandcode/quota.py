"""Command Code usage handler — published credit caps + local estimate.

No upstream usage API is documented. Caps come from ``RATE_LIMITS``
(docs, whole USD). ``used`` is summed from this connection's
``usage_history.cost`` (9Router token-pricing estimate — not
Command Code's official credit meter). ``accountType`` is 9Router
farm metadata only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.providers.commandcode.config import (
    PLANS_WITHOUT_PROVIDER_API,
    CommandcodeConfig,
    normalize_studio_plan,
)
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

_CONFIG = CommandcodeConfig()
_STUDIO_NOTE = (
    "Official caps from Command Code docs. Used bars are 9Router "
    "proxy cost estimates (usage_history) — compare spend in Studio."
)


def studio_plan_from_data(provider_data: dict | None) -> str | None:
    """Read the Studio subscription tier from connection data."""
    if not isinstance(provider_data, dict):
        return None
    raw = provider_data.get("studioPlan")
    if raw is None:
        raw = provider_data.get("studio_plan")
    return normalize_studio_plan(
        str(raw).strip() if raw is not None else None
    )


def resolve_plan(studio_plan: str | None) -> str | None:
    """Canonical RATE_LIMITS key for a Studio subscription tier."""
    if not studio_plan:
        return None
    mapped = _CONFIG.STUDIO_PLAN_ALIASES.get(studio_plan, studio_plan)
    if mapped in _CONFIG.RATE_LIMITS:
        return mapped
    return None


def lookup_limits(studio_plan: str | None = None) -> dict[str, int]:
    """Published credit window caps for the Studio tier (USD dollars)."""
    plan = resolve_plan(studio_plan)
    if not plan:
        return {}
    row = _CONFIG.RATE_LIMITS.get(plan) or {}
    return dict(row)


def _month_start_utc(now: datetime) -> datetime:
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


async def _sum_cost_cents(
    connection_id: str | None,
    since: datetime | None,
) -> int:
    """Sum proxy-estimated USD cost (cents) for this connection."""
    from sqlalchemy import func, select

    from app.database import async_session
    from app.models.usage import UsageHistory

    conditions = [
        func.lower(UsageHistory.provider) == _CONFIG.PROVIDER_ID,
        UsageHistory.status == "ok",
    ]
    if since is not None:
        conditions.append(UsageHistory.timestamp >= since)
    cid = _cid_key(connection_id)
    if cid:
        stored = func.replace(
            func.lower(
                func.coalesce(UsageHistory.connection_id, "")
            ),
            "-",
            "",
        )
        conditions.append(stored == cid)

    async with async_session() as db:
        result = await db.execute(
            select(
                func.coalesce(func.sum(UsageHistory.cost), 0.0),
            ).where(*conditions)
        )
        dollars = float(result.scalar() or 0.0)
    return max(0, int(round(dollars * 100)))


async def local_window_costs_cents(
    connection_id: str | None,
) -> tuple[int, int, int]:
    """Rolling-window proxy cost (cents): month, 5h, weekly."""
    now = datetime.now(timezone.utc)
    monthly = await _sum_cost_cents(
        connection_id,
        _month_start_utc(now),
    )
    five_h = await _sum_cost_cents(
        connection_id,
        now - timedelta(hours=5),
    )
    weekly = await _sum_cost_cents(
        connection_id,
        now - timedelta(days=7),
    )
    return monthly, five_h, weekly


def credit_bars(
    limits: dict[str, int],
    *,
    used_monthly_cents: int = 0,
    used_5h_cents: int = 0,
    used_weekly_cents: int = 0,
) -> list[dict[str, object]]:
    """Credit window bars — totals in USD cents for the quota UI."""
    used_by_key = {
        "monthly": used_monthly_cents,
        "window_5h": used_5h_cents,
        "weekly": used_weekly_cents,
    }
    labels = (
        ("monthly", "Monthly credits (USD, est.)"),
        ("window_5h", "5-hour window (USD, est.)"),
        ("weekly", "Weekly window (USD, est.)"),
    )
    rows: list[dict[str, object]] = []
    for key, name in labels:
        total_usd = int(limits.get(key) or 0)
        if total_usd <= 0:
            continue
        total_cents = total_usd * 100
        used = min(int(used_by_key.get(key) or 0), total_cents)
        remaining = max(0, total_cents - used)
        pct = (
            100.0
            if total_cents <= 0
            else max(0.0, remaining / total_cents * 100)
        )
        rows.append({
            "name": name,
            "used": used,
            "total": total_cents,
            "remaining": remaining,
            "remaining_percentage": pct,
            "reset_at": None,
            "unlimited": False,
        })
    return rows


def published_credit_bars(
    limits: dict[str, int],
) -> list[dict[str, object]]:
    """Backward-compatible alias — zero used."""
    return credit_bars(limits)


class CommandcodeUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "commandcode"
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del access_token
        studio_plan = studio_plan_from_data(provider_data)
        plan = resolve_plan(studio_plan)

        if not plan:
            return UsageResponse(
                plan=None,
                quotas=[],
                message=(
                    "Set Studio subscription plan (studioPlan) on "
                    "this connection: Go, GOAT, Pro, Max, Team Pro, "
                    "or Provider."
                ),
            )

        limits = lookup_limits(plan)

        if plan in PLANS_WITHOUT_PROVIDER_API:
            return UsageResponse(
                plan=plan,
                quotas=[],
                message=(
                    "Go plan: Studio web credits apply in Command "
                    "Code UI, but Provider API (/chat/completions, "
                    "/messages) returns 403 upgrade_required. "
                    "Upgrade to GOAT or higher for API routing."
                ),
            )

        if plan == "provider":
            return UsageResponse(
                plan=plan,
                quotas=[],
                message=(
                    "Provider subscription: no rolling credit windows "
                    "in docs; extra credits are uncapped. "
                    f"{_STUDIO_NOTE}"
                ),
            )

        monthly, five_h, weekly = (0, 0, 0)
        if connection_id:
            monthly, five_h, weekly = await local_window_costs_cents(
                connection_id,
            )

        rows = credit_bars(
            limits,
            used_monthly_cents=monthly,
            used_5h_cents=five_h,
            used_weekly_cents=weekly,
        )
        quotas = [QuotaItem(**row) for row in rows]

        if not quotas:
            return UsageResponse(
                plan=plan,
                quotas=[],
                message=_STUDIO_NOTE,
            )

        return UsageResponse(
            plan=plan,
            quotas=quotas,
            message=_STUDIO_NOTE,
        )
