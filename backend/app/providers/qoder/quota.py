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

import logging
from datetime import datetime, timezone

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
    cap = int(total) if total is not None else published_credit_cap()
    if remaining is not None:
        left = int(remaining)
        used = max(0, cap - left)
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


class QoderUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "qoder"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        del connection_id
        blob = provider_data or {}
        stored = usage_from_stored(blob)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = await self._get(QODER_QUOTA_USAGE_URL, headers)
        except Exception as e:
            logger.warning("Qoder usage fetch failed: %s", e)
            if stored is not None:
                return stored
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            if stored is not None:
                return stored
            return UsageResponse(
                message=(
                    f"Qoder API returned {resp.status_code}"
                )
            )

        data = resp.json()
        quota = data.get("userQuota") or {}
        total = int(quota.get("total", 0)) or published_credit_cap()
        used = int(quota.get("used", 0))
        remaining = int(
            quota.get("remaining", max(0, total - used))
        )
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

        return UsageResponse(
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
