"""Qoder usage handler.

Endpoint: QODER_QUOTA_USAGE_URL (providers/qoder/constants.py)
Auth: OAuth Bearer token.

Response shape (verified 2026-08):
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

from app.providers.qoder.constants import (
    QODER_QUOTA_USAGE_URL,
)

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)


class QoderUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "qoder"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = await self._get(QODER_QUOTA_USAGE_URL, headers)
        except Exception as e:
            logger.warning("Qoder usage fetch failed: %s", e)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            return UsageResponse(
                message=(
                    f"Qoder API returned {resp.status_code}"
                )
            )

        data = resp.json()
        quota = data.get("userQuota") or {}
        total = int(quota.get("total", 0))
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

        return UsageResponse(
            plan=data.get("userType"),
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
