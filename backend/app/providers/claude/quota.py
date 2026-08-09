"""Claude (Anthropic) usage handler.

Endpoint: GET https://api.anthropic.com/v1/usage
Auth: OAuth Bearer token
Headers: anthropic-beta: oauth-2025-04-20

Response fields are utilization percentages (0-100 = % used).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/usage"

# Map response keys to display names
QUOTA_NAMES = {
    "five_hour": "Session (5h)",
    "seven_day": "Weekly (7d)",
    "seven_day_sonnet": "Weekly Sonnet",
    "seven_day_opus": "Weekly Opus",
}


def _ts_to_iso(ts: int | float | None) -> str | None:
    """Convert unix timestamp to ISO 8601 string."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(
            ts, tz=timezone.utc
        ).isoformat()
    except (ValueError, OSError):
        return None


class ClaudeUsageHandler(BaseUsageHandler):
    PROVIDER_ID = "claude"

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "anthropic-beta": "oauth-2025-04-20",
        }

        try:
            resp = await self._get(API_URL, headers)
        except Exception as e:
            logger.warning("Claude usage fetch failed: %s", e)
            return UsageResponse(
                message=f"Failed to fetch: {e}"
            )

        if resp.status_code == 429:
            return UsageResponse(
                message="Rate limited — try again later"
            )

        if resp.status_code != 200:
            return UsageResponse(
                message=(
                    f"Claude API returned {resp.status_code}"
                )
            )

        data = resp.json()
        quotas: list[QuotaItem] = []
        limit_reached = False

        for key, display_name in QUOTA_NAMES.items():
            entry = data.get(key)
            if not entry or not isinstance(entry, dict):
                continue

            utilization = entry.get("utilization", 0)
            resets_at = entry.get("resets_at")

            # utilization = % used, so remaining = 100 - used
            remaining_pct = max(0.0, 100.0 - utilization)
            if remaining_pct <= 0:
                limit_reached = True

            quotas.append(QuotaItem(
                name=display_name,
                used=int(utilization),
                total=100,
                remaining=int(remaining_pct),
                remaining_percentage=remaining_pct,
                reset_at=_ts_to_iso(resets_at),
            ))

        return UsageResponse(
            plan="Pro",
            quotas=quotas,
            limit_reached=limit_reached,
        )
