"""GitHub Copilot usage handler.

Endpoint: GET https://api.github.com/copilot_internal/user
Auth: GitHub OAuth token (Authorization: token {accessToken})
"""

from __future__ import annotations

import logging

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.github.com/copilot_internal/user"


class GitHubUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "github"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
    ) -> UsageResponse:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/json",
            "User-Agent": "9Router-QuotaTracker",
        }

        try:
            resp = await self._get(API_URL, headers)
        except Exception as e:
            logger.warning("GitHub usage fetch failed: %s", e)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            return UsageResponse(
                message=f"GitHub API returned {resp.status_code}"
            )

        data = resp.json()
        plan = data.get("copilot_plan", "")
        quotas: list[QuotaItem] = []

        # Paid plan: quota_snapshots
        snapshots = data.get("quota_snapshots", {})
        reset_date = data.get("quota_reset_date")

        if snapshots:
            for key, snap in snapshots.items():
                entitlement = snap.get("entitlement", 0)
                remaining = snap.get("remaining", 0)
                is_unlimited = snap.get("unlimited", False)
                used = max(0, entitlement - remaining)

                quotas.append(QuotaItem(
                    name=key.replace("_", " ").title(),
                    used=used,
                    total=entitlement,
                    remaining=remaining,
                    remaining_percentage=(
                        100.0 if is_unlimited
                        else self._pct(used, entitlement)
                    ),
                    reset_at=reset_date,
                    unlimited=is_unlimited,
                ))
            return UsageResponse(
                plan=plan.title() if plan else None,
                quotas=quotas,
            )

        # Free plan: monthly_quotas + limited_user_quotas
        monthly = data.get("monthly_quotas", {})
        limited = data.get("limited_user_quotas", {})
        reset_date = data.get(
            "limited_user_reset_date",
            data.get("quota_reset_date"),
        )

        source = limited or monthly
        for key, total in source.items():
            quotas.append(QuotaItem(
                name=key.replace("_", " ").title(),
                used=0,
                total=total if isinstance(total, int) else 0,
                remaining=(
                    total if isinstance(total, int) else None
                ),
                remaining_percentage=100.0,
                reset_at=reset_date,
            ))

        return UsageResponse(
            plan="Free" if not plan else plan.title(),
            quotas=quotas,
            message=(
                "Free plan — used count not available"
                if limited or monthly else None
            ),
        )
