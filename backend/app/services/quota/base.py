"""Base usage handler and shared quota schemas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx
from pydantic import BaseModel


class QuotaItem(BaseModel):
    """A single quota metric from a provider."""

    name: str
    used: int = 0
    total: int = 0
    remaining: Optional[int] = None
    remaining_percentage: float = 100.0
    reset_at: Optional[str] = None
    unlimited: bool = False


class UsageResponse(BaseModel):
    """Standardized usage response from any provider."""

    plan: Optional[str] = None
    quotas: list[QuotaItem] = []
    message: Optional[str] = None
    limit_reached: bool = False


class BaseUsageHandler(ABC):
    """Abstract base for provider-specific usage fetchers."""

    PROVIDER_ID: str = ""
    TIMEOUT: float = 15.0
    # False for handlers that derive usage from local state
    # (e.g. recorded upstream errors) instead of polling an
    # upstream API — the router skips quota_cache for these so
    # results always reflect the current connection state.
    USES_UPSTREAM: bool = True

    @abstractmethod
    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        """Fetch usage/quota data from the provider API.

        Args:
            access_token: OAuth access token or API key.
            provider_data: Extra provider-specific data from
                the connection's JSON blob.
            connection_id: Connection UUID string, for handlers
                that derive usage from local records.

        Returns:
            Standardized UsageResponse.
        """

    async def observe_response(
        self,
        db: Any,
        connection_id: str,
        headers: Any,
        model: str | None = None,
    ) -> None:
        """Optional PS hook: record rate-limit headers.

        Default: no-op. Dispatcher fail-open.
        """

    async def observe_complete(
        self,
        db: Any,
        connection_id: str,
    ) -> None:
        """Optional PS hook: after usage_history is written.

        Default: no-op. For providers whose ``used`` is not in
        that log (Qoder credits), poll the live quota API here.
        """
        del db, connection_id

    async def _get(
        self,
        url: str,
        headers: dict[str, str],
        params: dict | None = None,
    ) -> httpx.Response:
        """Shared HTTP GET with timeout."""
        async with httpx.AsyncClient(
            timeout=self.TIMEOUT
        ) as client:
            return await client.get(
                url, headers=headers, params=params
            )

    @staticmethod
    def _pct(used: int, total: int) -> float:
        """Calculate remaining percentage."""
        if total <= 0:
            return 100.0
        return max(0.0, ((total - used) / total) * 100)
