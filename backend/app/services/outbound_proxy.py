"""Outbound proxy usage resolution and httpx client factory."""

from __future__ import annotations

import contextvars
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

import httpx
from sqlalchemy import select

from app.models.proxy_pool import ProxyPool

ProxyPurpose = Literal[
    "testConnection",
    "testModel",
    "testChat",
    "oauthRefresh",
    "upstream",
]

DEFAULT_PROXY_USAGE: dict[str, Any] = {
    "mode": "off",
    "flags": {
        "testConnection": False,
        "testModel": False,
        "testChat": False,
        "oauthRefresh": False,
    },
}

_outbound_proxy_var: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("outbound_proxy", default=None)
)

_HEADER_TO_PURPOSE: dict[str, ProxyPurpose] = {
    "test-chat": "testChat",
}


class ProxyRequiredError(Exception):
    """Raised when proxy is required but pool is missing or inactive."""


def parse_proxy_usage(data: dict | None) -> dict:
    """Return normalized proxy usage from raw JSON data."""
    if not data:
        return {
            "mode": DEFAULT_PROXY_USAGE["mode"],
            "flags": dict(DEFAULT_PROXY_USAGE["flags"]),
        }

    raw_flags = data.get("flags") or {}
    flags = dict(DEFAULT_PROXY_USAGE["flags"])
    for key in flags:
        if key in raw_flags:
            flags[key] = bool(raw_flags[key])

    mode = data.get("mode", DEFAULT_PROXY_USAGE["mode"])
    if mode not in ("off", "selective", "all"):
        mode = DEFAULT_PROXY_USAGE["mode"]

    return {"mode": mode, "flags": flags}


def purpose_from_header(value: str | None) -> ProxyPurpose:
    """Map X-9Router-Purpose header value to a proxy purpose."""
    if not value:
        return "upstream"
    return _HEADER_TO_PURPOSE.get(value.strip().lower(), "upstream")


def should_use_proxy(usage: dict, purpose: ProxyPurpose) -> bool:
    """Return True when outbound traffic for purpose should use a proxy."""
    normalized = parse_proxy_usage(usage)
    mode = normalized["mode"]
    flags = normalized["flags"]

    if mode == "all":
        return True
    if mode == "selective" and purpose != "upstream":
        return bool(flags.get(purpose, False))
    return False


def resolve_proxy_url(
    *,
    usage: dict,
    purpose: ProxyPurpose,
    pool: ProxyPool | None,
) -> str | None:
    """Resolve proxy URL for purpose, or None for direct connection."""
    if not should_use_proxy(usage, purpose):
        return None

    if pool is None or not pool.is_active:
        if pool is not None and pool.strict_proxy:
            raise ProxyRequiredError(
                "Proxy required but pool is inactive or unavailable"
            )
        return None

    return pool.proxy_url


async def proxy_for_connection(
    db: Any,
    conn: Any | None,
    purpose: ProxyPurpose,
) -> str | None:
    """Resolve the proxy URL for one provider connection and purpose."""
    if conn is None:
        return None

    try:
        data = json.loads(conn.data) if conn.data else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    usage = parse_proxy_usage(data.get("proxyUsage"))
    if not should_use_proxy(usage, purpose):
        return None

    pool = None
    if conn.proxy_pool_id:
        result = await db.execute(
            select(ProxyPool).where(ProxyPool.id == conn.proxy_pool_id)
        )
        pool = result.scalar_one_or_none()

    return resolve_proxy_url(
        usage=usage,
        purpose=purpose,
        pool=pool,
    )


def create_upstream_client(
    *,
    proxy: str | None = None,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Create httpx.AsyncClient with optional outbound proxy."""
    effective_proxy = proxy
    if effective_proxy is None:
        effective_proxy = _outbound_proxy_var.get()

    client_kwargs = dict(kwargs)
    client_kwargs["timeout"] = timeout
    if effective_proxy:
        client_kwargs["proxy"] = effective_proxy
    return httpx.AsyncClient(**client_kwargs)


@asynccontextmanager
async def use_outbound_proxy(
    proxy: str | None,
) -> AsyncIterator[None]:
    """Set ContextVar so nested create_upstream_client inherits proxy."""
    token = _outbound_proxy_var.set(proxy)
    try:
        yield
    finally:
        _outbound_proxy_var.reset(token)


def merge_proxy_usage_into_data(data: dict, usage: dict) -> dict:
    """Copy connection data and set normalized proxyUsage."""
    out = dict(data)
    out["proxyUsage"] = parse_proxy_usage(usage)
    return out
