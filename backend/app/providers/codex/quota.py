"""Codex (OpenAI) usage handler.

Endpoint: GET https://api.openai.com/v1/usage
Auth: OAuth Bearer token

Response uses used_percent (0-100 = % used) per window.
"""

from __future__ import annotations

import logging

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.openai.com/v1/usage"

WINDOW_NAMES = {
    "primary_window": "Session",
    "secondary_window": "Weekly",
}


class CodexUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "codex"

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
            logger.warning("Codex usage fetch failed: %s", e)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code != 200:
            return UsageResponse(
                message=(
                    f"OpenAI API returned {resp.status_code}"
                )
            )

        data = resp.json()
        plan_type = data.get("plan_type", "")
        rate_limit = data.get("rate_limit", {})
        quotas: list[QuotaItem] = []
        limit_reached = False

        for key, display_name in WINDOW_NAMES.items():
            window = rate_limit.get(key)
            if not window or not isinstance(window, dict):
                continue

            used_pct = window.get("used_percent", 0)
            reset_at = window.get("reset_at")
            remaining_pct = max(0.0, 100.0 - used_pct)

            if remaining_pct <= 0:
                limit_reached = True

            quotas.append(QuotaItem(
                name=display_name,
                used=int(used_pct),
                total=100,
                remaining=int(remaining_pct),
                remaining_percentage=remaining_pct,
                reset_at=reset_at,
            ))

        # Review credits (if available)
        credits = data.get(
            "rate_limit_reset_credits", {}
        )
        available = credits.get("available_count")
        if available is not None:
            quotas.append(QuotaItem(
                name="Reset Credits",
                used=0,
                total=available,
                remaining=available,
                remaining_percentage=100.0,
            ))

        return UsageResponse(
            plan=plan_type.title() if plan_type else None,
            quotas=quotas,
            limit_reached=limit_reached,
        )
