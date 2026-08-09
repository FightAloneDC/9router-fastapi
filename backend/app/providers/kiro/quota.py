"""Kiro (AWS CodeWhisperer) usage handler.

Endpoint: GET https://codewhisperer.us-east-1.amazonaws.com/getUsageLimits
Auth: OAuth Bearer token or API key
Headers: x-amz-user-agent: aws-sdk-js/1.0.0 KiroIDE
"""

from __future__ import annotations

import logging

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)

API_URL = (
    "https://codewhisperer.us-east-1.amazonaws.com"
    "/getUsageLimits"
)


class KiroUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "kiro"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-amz-user-agent": (
                "aws-sdk-js/1.0.0 KiroIDE"
            ),
        }

        try:
            resp = await self._get(API_URL, headers)
        except Exception as e:
            logger.warning("Kiro usage fetch failed: %s", e)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            return UsageResponse(
                message=(
                    f"Kiro API returned {resp.status_code}"
                )
            )

        data = resp.json()
        sub_info = data.get("subscriptionInfo", {})
        plan = sub_info.get("subscriptionTitle", "")
        breakdown = data.get("usageBreakdownList", [])
        quotas: list[QuotaItem] = []
        limit_reached = False

        for item in breakdown:
            resource = item.get("resourceType", "unknown")
            current = item.get(
                "currentUsageWithPrecision", 0
            )
            limit = item.get(
                "usageLimitWithPrecision", 0
            )
            reset_at = item.get("nextDateReset")

            used = int(current)
            total = int(limit)
            remaining_pct = self._pct(used, total)

            if remaining_pct <= 0:
                limit_reached = True

            name = resource.replace("_", " ").title()
            quotas.append(QuotaItem(
                name=name,
                used=used,
                total=total,
                remaining=max(0, total - used),
                remaining_percentage=remaining_pct,
                reset_at=reset_at,
            ))

        return UsageResponse(
            plan=plan or None,
            quotas=quotas,
            limit_reached=limit_reached,
        )
