"""Qoder usage handler.

Endpoint: GET https://api.qoder.dev/v1/user/usage
Auth: OAuth Bearer token
"""

from __future__ import annotations

import logging

from .base import BaseUsageHandler, QuotaItem, UsageResponse

logger = logging.getLogger(__name__)

API_URL = "https://api.qoder.dev/v1/user/usage"


class QoderUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "qoder"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
    ) -> UsageResponse:
        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        try:
            resp = await self._get(API_URL, headers)
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
        raw_quotas = data.get("quotas", {})
        quotas: list[QuotaItem] = []
        limit_reached = False

        for key, q in raw_quotas.items():
            if not isinstance(q, dict):
                continue

            total = q.get("total", 0)
            used = q.get("used", 0)
            remaining = q.get(
                "remaining", max(0, total - used)
            )
            reset_at = q.get("resetAt")
            remaining_pct = self._pct(used, total)

            if remaining_pct <= 0:
                limit_reached = True

            quotas.append(QuotaItem(
                name=key.title(),
                used=used,
                total=total,
                remaining=remaining,
                remaining_percentage=remaining_pct,
                reset_at=reset_at,
            ))

        return UsageResponse(
            quotas=quotas,
            limit_reached=limit_reached,
        )
