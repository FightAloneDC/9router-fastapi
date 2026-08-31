"""DeepSeek usage handler — balance API + local signup token bar.

Signup grant: ~5M tokens, ~30 days from registration
(operator 2026-08-26; DeepSeek platform docs).

Upstream: GET /user/balance (granted + topped-up USD/CNY).
Docs publish concurrency per model, not fixed RPM/TPM.

Local: this connection's usage_history token sum vs the
published signup_grant token cap (complements balance API).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from app.database import async_session
from app.models.provider import ProviderConnection
from app.models.usage import UsageHistory
from app.providers.deepseek.config import DeepseekConfig
from app.services.quota.base import (
    BaseUsageHandler,
    QuotaItem,
    UsageResponse,
)

logger = logging.getLogger(__name__)

BALANCE_URL = "https://api.deepseek.com/user/balance"
_CONFIG = DeepseekConfig()


def resolve_plan(provider_data: dict | None) -> str:
    """UI accountType on the connection (free / payg / subscribe)."""
    raw = ""
    if isinstance(provider_data, dict):
        raw = str(
            provider_data.get("accountType")
            or provider_data.get("account_type")
            or ""
        ).strip().lower()
    if raw in ("payg", "subscribe"):
        return raw
    return "free"


def signup_token_grant() -> int:
    """Published signup token grant from RATE_LIMITS."""
    row = _CONFIG.RATE_LIMITS.get("signup_grant") or {}
    return int(row.get("tokens") or 5_000_000)


def signup_grant_days() -> int:
    """Signup grant validity window from RATE_LIMITS."""
    row = _CONFIG.RATE_LIMITS.get("signup_grant") or {}
    return int(row.get("days") or 30)


def signup_grant_value_usd_cents() -> int:
    """Marketed grant value for the granted-balance bar."""
    row = _CONFIG.RATE_LIMITS.get("signup_grant") or {}
    return int(row.get("value_usd_cents") or 840)


def lookup_concurrency(model_id: str) -> int | None:
    """Published concurrent-request cap for a model id."""
    key = (model_id or "").strip()
    if key.startswith("ds/"):
        key = key[3:]
    table = _CONFIG.RATE_LIMITS
    if key in table:
        cap = table[key].get("concurrency")
        return int(cap) if cap is not None else None
    return None


def _usd_cents(value: Any) -> int:
    try:
        return int(round(float(value or 0) * 100))
    except (TypeError, ValueError):
        return 0


def _pick_balance_row(balance_infos: list[dict]) -> dict:
    for row in balance_infos or []:
        if str(row.get("currency") or "").upper() == "USD":
            return row
    if balance_infos:
        return balance_infos[0]
    return {}


def _item(
    name: str,
    *,
    used: int,
    total: int,
    reset_at: str | None = None,
) -> dict[str, Any]:
    remaining = max(0, total - used) if total else 0
    if total <= 0:
        pct = 100.0
    else:
        pct = max(0.0, remaining / total * 100)
    return {
        "name": name,
        "used": min(used, total) if total else used,
        "total": total,
        "remaining": remaining,
        "remaining_percentage": pct,
        "reset_at": reset_at,
        "unlimited": total <= 0,
    }


def _usd_grant_item(
    *,
    used_cents: int,
    total_cents: int,
    reset_at: str | None = None,
) -> dict[str, Any]:
    """Signup grant USD consumed vs published reference cap."""
    return _item(
        "Granted balance (USD)",
        used=used_cents,
        total=total_cents,
        reset_at=reset_at,
    )


def _usd_wallet_item(cents: int) -> dict[str, Any]:
    """Prepaid / available USD left (not a used-vs-cap meter)."""
    amount = max(0, int(cents))
    return {
        "name": "API balance (USD)",
        "used": 0,
        "total": amount,
        "remaining": amount,
        "remaining_percentage": 100.0,
        "reset_at": None,
        "unlimited": False,
    }


def balance_quota_rows(
    payload: dict,
    *,
    reset_at: str | None = None,
    free_summary: bool = False,
) -> list[dict[str, Any]]:
    """Build quota bars from GET /user/balance JSON."""
    row = _pick_balance_row(payload.get("balance_infos") or [])
    granted = _usd_cents(row.get("granted_balance"))
    topped = _usd_cents(row.get("topped_up_balance"))
    total = _usd_cents(row.get("total_balance"))
    rows: list[dict[str, Any]] = []

    if free_summary:
        if total > 0:
            rows.append(_usd_wallet_item(total))
        return rows

    reference = signup_grant_value_usd_cents()
    if granted > 0:
        cap = max(reference, granted)
        used = max(0, cap - granted)
        rows.append(
            _usd_grant_item(
                used_cents=used,
                total_cents=cap,
                reset_at=reset_at,
            )
        )
    elif total > 0:
        rows.append(_usd_wallet_item(total))
    elif topped > 0:
        rows.append(_usd_wallet_item(topped))
    return rows


def _cid_key(value: str | None) -> str:
    return (value or "").replace("-", "").lower()


async def lifetime_tokens(connection_id: str | None) -> int:
    """Token sum for this connection in usage_history."""
    conditions = [
        func.lower(UsageHistory.provider) == _CONFIG.PROVIDER_ID,
    ]
    cid = _cid_key(connection_id)
    if cid:
        stored = func.replace(
            func.lower(
                func.coalesce(UsageHistory.connection_id, ""),
            ),
            "-",
            "",
        )
        conditions.append(stored == cid)

    async with async_session() as db:
        result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        UsageHistory.prompt_tokens
                        + UsageHistory.completion_tokens
                    ),
                    0,
                )
            ).where(*conditions)
        )
        return int(result.scalar() or 0)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00"),
        )
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _connection_api_key(
    access_token: str,
    provider_data: dict | None,
) -> str:
    """Bearer token from fetch arg or connection data blob."""
    data = provider_data if isinstance(provider_data, dict) else {}
    for raw in (
        access_token,
        data.get("apiKey"),
        data.get("accessToken"),
    ):
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def _local_free_rows(
    *,
    connection_id: str | None,
    grant_reset: str | None,
    used_tokens: int,
) -> list[dict[str, Any]]:
    """Signup token bar without an upstream balance poll."""
    return [
        _item(
            "Signup grant tokens",
            used=used_tokens,
            total=signup_token_grant(),
            reset_at=grant_reset,
        ),
    ]


async def grant_expires_at(
    connection_id: str | None,
    provider_data: dict | None = None,
) -> str | None:
    """Grant expiry ISO timestamp for the signup window.

    Prefers connection data ``grantExpiresAt`` or
    ``grantRegisteredAt`` + published days; otherwise
    ``provider_connections.created_at`` + days.
    """
    data = provider_data if isinstance(provider_data, dict) else {}
    explicit = _parse_iso(str(data.get("grantExpiresAt") or ""))
    if explicit is not None:
        return explicit.isoformat()

    registered = _parse_iso(str(data.get("grantRegisteredAt") or ""))
    if registered is not None:
        expires = registered + timedelta(days=signup_grant_days())
        return expires.isoformat()

    if not connection_id:
        return None

    async with async_session() as db:
        result = await db.execute(
            select(ProviderConnection).where(
                ProviderConnection.id == connection_id,
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None or conn.created_at is None:
            return None
        created = conn.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        expires = created + timedelta(days=signup_grant_days())
        return expires.isoformat()


class DeepseekUsageHandler(BaseUsageHandler):
    """Balance API + local signup token consumption."""

    PROVIDER_ID = _CONFIG.PROVIDER_ID
    USES_UPSTREAM = False

    async def fetch(
        self,
        access_token: str,
        provider_data: dict | None = None,
        connection_id: str | None = None,
    ) -> UsageResponse:
        plan = resolve_plan(provider_data)
        grant_reset = await grant_expires_at(
            connection_id, provider_data,
        )
        api_key = _connection_api_key(access_token, provider_data)
        if not api_key:
            rows: list[dict[str, Any]] = []
            if plan == "free":
                used_tokens = await lifetime_tokens(connection_id)
                rows = _local_free_rows(
                    connection_id=connection_id,
                    grant_reset=grant_reset,
                    used_tokens=used_tokens,
                )
            return UsageResponse(
                plan=plan,
                quotas=[QuotaItem(**row) for row in rows],
                message="No API key found on this connection.",
            )

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        try:
            resp = await self._get(BALANCE_URL, headers)
        except Exception as e:
            logger.warning("DeepSeek balance fetch failed: %s", e)
            return UsageResponse(
                plan=plan,
                message=f"Failed to fetch: {e}",
            )

        if resp.status_code != 200:
            return UsageResponse(
                plan=plan,
                message=(
                    f"DeepSeek API returned {resp.status_code}"
                ),
            )

        payload = resp.json()
        rows: list[dict[str, Any]] = []
        if plan == "free":
            used_tokens = await lifetime_tokens(connection_id)
            rows.append(
                _item(
                    "Signup grant tokens",
                    used=used_tokens,
                    total=signup_token_grant(),
                    reset_at=grant_reset,
                )
            )
            rows.extend(
                balance_quota_rows(
                    payload,
                    free_summary=True,
                )
            )
        else:
            rows.extend(balance_quota_rows(payload))

        granted = _usd_cents(
            _pick_balance_row(
                payload.get("balance_infos") or [],
            ).get("granted_balance"),
        )
        available = bool(payload.get("is_available", True))
        used_tokens = await lifetime_tokens(connection_id)
        token_exhausted = (
            plan == "free"
            and used_tokens >= signup_token_grant()
            and granted <= 0
        )
        grant_expired = False
        if grant_reset:
            expires = _parse_iso(grant_reset)
            if expires is not None:
                grant_expired = expires <= datetime.now(timezone.utc)

        return UsageResponse(
            plan=plan,
            quotas=[QuotaItem(**row) for row in rows],
            limit_reached=(
                not available or token_exhausted or grant_expired
            ),
            message=(
                "Free signup grant: "
                f"{signup_token_grant():,} tokens, "
                f"{signup_grant_days()} days from registration "
                "(connection created_at unless grantRegisteredAt "
                "is set on the connection). Balance from "
                "GET /user/balance."
            ),
        )
