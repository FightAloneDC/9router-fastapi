"""Qoder usage handler.

Endpoint: QODER_QUOTA_USAGE_URL (providers/qoder/constants.py)
Auth: OAuth Bearer token (not COSY).

Published trial cap: QoderConfig.RATE_LIMITS["trial"]
(credits + days). Live used/remaining/expiresAt come from the
quota API. Response shape (verified 2026-08):

  {"userType": "personal_professional_trial",
   "usageType": "credits",
   "isQuotaExceeded": true,
   "expiresAt": 1787423063188,
   "userQuota": {"total": 300.0, "used": 300.0,
                 "remaining": 0.0, "percentage": 1.0,
                 "unit": "credits"}, ...}
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.usage import UsageHistory
from app.providers.qoder.bulk import parse_expires_at
from app.providers.qoder.config import QoderConfig
from app.providers.qoder.constants import (
    QODER_QUOTA_USAGE_URL,
)

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)


def published_credit_cap() -> int:
    """Trial credit total from RATE_LIMITS (Provider Detail table)."""
    table = QoderConfig().RATE_LIMITS
    return int(table.get("trial", {}).get("credits") or 300)


def as_credit(value: Any, default: float = 0.0) -> float:
    """Parse a credit field. Never int() or round."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def credits_from_tokens(raw: dict | str | None) -> float:
    """Credits charged on one chat (SSE ``usage`` / usage_history).

    Return the full float. Never int() or round.
    """
    if raw is None:
        return 0.0
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return 0.0
    elif isinstance(raw, dict):
        data = raw
    else:
        return 0.0
    val = data.get("credits")
    if val is None:
        val = data.get("original_credits")
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        return 0.0


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


async def local_credits(connection_id: str | None) -> float:
    """Sum ``usage_history.tokens.credits`` for this connection."""
    cid = _cid_key(connection_id)
    if not cid:
        return 0.0
    stored = func.replace(
        func.lower(func.coalesce(UsageHistory.connection_id, "")),
        "-",
        "",
    )
    async with async_session() as db:
        rows = (
            await db.execute(
                select(UsageHistory.tokens).where(
                    func.lower(UsageHistory.provider) == "qoder",
                    stored == cid,
                )
            )
        ).all()
    total = 0.0
    for (raw,) in rows:
        total += credits_from_tokens(raw)
    return total


def usage_from_stored(data: dict) -> UsageResponse | None:
    """Last stored quota/trial check on the connection, if any.

    Blob ``expiresAt`` is job-token TTL, not trial end — do
    not read it here. Trial window is ``proTrialEndAt``.
    """
    total = data.get("farmQuotaTotal")
    remaining = data.get("farmQuotaRemaining")
    exceeded = data.get("farmQuotaExceeded")
    reset_at = parse_expires_at(data.get("proTrialEndAt"))
    has_credits = (
        total is not None
        or remaining is not None
        or exceeded is not None
    )
    if not has_credits and reset_at is None:
        return None
    plan = data.get("userType") or data.get("plan")
    plan_s = str(plan) if plan else None
    if not has_credits:
        return UsageResponse(
            plan=plan_s,
            quotas=[QuotaItem(
                name="Credits",
                reset_at=reset_at,
            )],
        )
    cap = (
        as_credit(total)
        if total is not None
        else float(published_credit_cap())
    )
    if remaining is not None:
        left = as_credit(remaining)
        used = max(0.0, cap - left)
    elif exceeded is True:
        left = 0
        used = cap
    else:
        used = 0
        left = cap
    hit = bool(exceeded) if exceeded is not None else left <= 0
    return UsageResponse(
        plan=plan_s,
        quotas=[QuotaItem(
            name="Credits",
            used=used,
            total=cap,
            remaining=left,
            remaining_percentage=QoderUsageHandler._pct(used, cap),
            reset_at=reset_at,
        )],
        limit_reached=hit,
    )


def apply_local_used(
    result: UsageResponse,
    local_used: float,
) -> UsageResponse:
    """Raise used to chat-log credits when they exceed API used."""
    if local_used <= 0:
        return result
    cap = float(published_credit_cap())
    if not result.quotas:
        left = max(0.0, cap - local_used)
        result.quotas = [QuotaItem(
            name="Credits",
            used=local_used,
            total=cap,
            remaining=left,
            remaining_percentage=QoderUsageHandler._pct(
                local_used, cap,
            ),
        )]
        result.limit_reached = left <= 0
        return result
    item = result.quotas[0]
    used = max(item.used, local_used)
    if used == item.used:
        return result
    total = item.total or cap
    left = max(0.0, total - used)
    result.quotas[0] = item.model_copy(update={
        "used": used,
        "remaining": left,
        "remaining_percentage": QoderUsageHandler._pct(
            used, total,
        ),
    })
    result.limit_reached = result.limit_reached or left <= 0
    return result


class QoderUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "qoder"
    # Same list path as other FLOW.md quota providers: GET /quota
    # calls fetch() for visible rows (60s tracker tick). fetch()
    # still GETs QODER_QUOTA_USAGE_URL.
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        blob = provider_data or {}
        stored = usage_from_stored(blob)
        local_used = await local_credits(connection_id)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = await self._get(QODER_QUOTA_USAGE_URL, headers)
        except Exception as e:
            logger.warning("Qoder usage fetch failed: %s", e)
            if stored is not None:
                return apply_local_used(stored, local_used)
            if local_used:
                return apply_local_used(UsageResponse(), local_used)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            if stored is not None:
                return apply_local_used(stored, local_used)
            if local_used:
                return apply_local_used(UsageResponse(), local_used)
            return UsageResponse(
                message=(
                    f"Qoder API returned {resp.status_code}"
                )
            )

        data = resp.json()
        quota = data.get("userQuota") or {}
        total = as_credit(quota.get("total")) or float(
            published_credit_cap()
        )
        used = as_credit(quota.get("used"))
        remaining = quota.get("remaining")
        if remaining is None:
            remaining = max(0.0, total - used)
        else:
            remaining = as_credit(remaining)
        unit = (quota.get("unit") or "credits").title()
        remaining_pct = self._pct(used, total)

        reset_at = None
        expires_ms = data.get("expiresAt")
        if isinstance(expires_ms, (int, float)) and expires_ms > 0:
            reset_at = datetime.fromtimestamp(
                expires_ms / 1000, tz=timezone.utc,
            ).isoformat()
        if reset_at is None:
            reset_at = parse_expires_at(blob.get("proTrialEndAt"))

        result = UsageResponse(
            plan=data.get("userType") or blob.get("userType"),
            quotas=[QuotaItem(
                name=unit,
                used=used,
                total=total,
                remaining=remaining,
                remaining_percentage=remaining_pct,
                reset_at=reset_at,
            )],
            limit_reached=bool(data.get("isQuotaExceeded"))
            or remaining <= 0,
        )
        return apply_local_used(result, local_used)

    async def observe_complete(
        self,
        db: Any,
        connection_id: str,
    ) -> None:
        """After a proxied chat, apply usage_history.tokens.credits.

        Live SSE usage carries ``credits`` (verified 2026-09-01).
        Same lifecycle as NVIDIA counting the log — no extra
        quota/usage GET here.
        """
        from app.models.quota_cache import QuotaCache

        local_used = await local_credits(connection_id)
        if local_used <= 0:
            return
        try:
            cid = uuid.UUID(connection_id)
        except (TypeError, ValueError):
            return
        cache = await db.get(QuotaCache, cid)
        cap = published_credit_cap()
        reset_at: str | None = None
        plan: str | None = None
        if cache is not None and cache.quotas:
            try:
                rows = json.loads(cache.quotas)
            except (json.JSONDecodeError, TypeError):
                rows = []
            if isinstance(rows, list) and rows:
                row0 = rows[0] if isinstance(rows[0], dict) else {}
                cap = as_credit(row0.get("total") or cap) or float(
                    cap
                )
                raw_reset = row0.get("reset_at")
                if isinstance(raw_reset, str):
                    reset_at = raw_reset
            plan = cache.plan
        left = max(0.0, float(cap) - local_used)
        result = UsageResponse(
            plan=plan,
            quotas=[QuotaItem(
                name="Credits",
                used=local_used,
                total=cap,
                remaining=left,
                remaining_percentage=self._pct(local_used, cap),
                reset_at=reset_at,
            )],
            limit_reached=left <= 0,
        )
        if cache is None:
            cache = QuotaCache(connection_id=cid)
            db.add(cache)
        cache.plan = result.plan
        cache.quotas = json.dumps(
            [q.model_dump() for q in result.quotas]
        )
        cache.limit_reached = result.limit_reached
        cache.fetched_at = datetime.now(timezone.utc)
        await db.commit()
