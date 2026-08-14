"""Core proxy service — resolve model to provider, forward request, stream response."""

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.combo import Combo
from app.models.provider import ProviderConnection, ProviderNode
from app.models.settings import SettingsModel
from app.providers.provider import Provider

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Frontend alias → backend provider ID mapping
# Matches the alias definitions in frontend/src/constants/providers.js
# ──────────────────────────────────────────────

def _build_alias_to_id() -> dict[str, str]:
    """Build alias → provider ID mapping from Provider class.

    Each provider's config has an ALIAS field. Also includes provider ID itself
    as a key (for cases like "openrouter" → "openrouter").
    When multiple providers share an alias (e.g. kilo-gateway + kilocode),
    the last one wins in this dict. Use ALIAS_TO_IDS for all matches.
    """
    from app.providers import AVAILABLE_PROVIDERS
    mapping: dict[str, str] = {}
    for name in AVAILABLE_PROVIDERS:
        try:
            p = Provider(name)
            alias: str = p.config().ALIAS
            if alias:
                mapping[alias] = name
            # Also map provider ID to itself (for "openrouter" → "openrouter")
            mapping[name] = name
        except (ValueError, ModuleNotFoundError):
            pass
    return mapping


def _build_alias_to_ids() -> dict[str, list[str]]:
    """Build alias → list of provider IDs mapping.

    Handles shared aliases (e.g. 'kilo' → ['kilo-gateway', 'kilocode']).
    Provider IDs are also included as keys mapping to themselves.
    """
    from app.providers import AVAILABLE_PROVIDERS
    mapping: dict[str, list[str]] = {}
    for name in AVAILABLE_PROVIDERS:
        try:
            p = Provider(name)
            alias: str = p.config().ALIAS
            if alias:
                mapping.setdefault(alias, []).append(name)
            mapping.setdefault(name, []).append(name)
        except (ValueError, ModuleNotFoundError):
            pass
    return mapping


def _build_id_to_alias() -> dict[str, str]:
    """Build provider ID → alias mapping directly from Provider class."""
    from app.providers import AVAILABLE_PROVIDERS
    mapping: dict[str, str] = {}
    for name in AVAILABLE_PROVIDERS:
        try:
            p = Provider(name)
            alias: str = p.config().ALIAS
            if alias:
                mapping[name] = alias
        except (ValueError, ModuleNotFoundError):
            pass
    return mapping


ALIAS_TO_ID: dict[str, str] = _build_alias_to_id()
ALIAS_TO_IDS: dict[str, list[str]] = _build_alias_to_ids()


def _resolve_provider_alias(provider_name: str) -> str:
    """Resolve a frontend provider alias to the backend provider ID.

    The frontend sends model strings like "an/claude-3-5-sonnet" where "an"
    is the storage alias for "anthropic". This function resolves the alias
    to the actual provider ID used in ProviderConnection.provider.
    """
    return ALIAS_TO_ID.get(provider_name, provider_name)


def _resolve_provider_aliases(provider_name: str) -> list[str]:
    """Resolve alias to ALL matching provider IDs (for shared aliases).

    Returns a list of provider IDs. For unique aliases, returns a single-item list.
    For shared aliases like 'kilo', returns ['kilo-gateway', 'kilocode'].
    """
    return ALIAS_TO_IDS.get(provider_name, [provider_name])

# Reverse mapping: provider ID → alias
ID_TO_ALIAS: dict[str, str] = _build_id_to_alias()

# ──────────────────────────────────────────────
# Provider URL/header configuration
# ──────────────────────────────────────────────

def _get_provider_proxy_config(provider: str) -> dict:
    """Get provider proxy config from Provider class (LEGACY — prefer handler methods).

    Returns dict with keys: base_url, format, auth_header, auth_prefix, extra_headers.
    Used as fallback when handler is not available.
    """
    try:
        p = Provider(provider)
        c = p.config()
        return {
            "base_url": c.BASE_URL,
            "format": c.FORMAT,
            "auth_header": c.AUTH_HEADER,
            "auth_prefix": c.AUTH_PREFIX,
            "extra_headers": c.EXTRA_HEADERS or {},
        }
    except (ValueError, ModuleNotFoundError):
        # Fallback for providers not in new system
        return {
            "base_url": "",
            "format": "openai",
            "auth_header": "Authorization",
            "auth_prefix": "Bearer ",
            "extra_headers": {},
        }


@dataclass
class ResolvedTarget:
    """A resolved upstream provider target."""
    url: str
    headers: dict[str, str]
    provider: str
    model: str
    connection_id: str | None = None


# ──────────────────────────────────────────────
# In-memory connection rotation state (per-process)
# ──────────────────────────────────────────────
_connection_rotation: dict[str, dict] = {}


def get_connection_rotation(provider_id: str) -> dict:
    """Get or initialize rotation state for a provider."""
    if provider_id not in _connection_rotation:
        _connection_rotation[provider_id] = {"index": 0, "count": 0}
    return _connection_rotation[provider_id]


def reset_connection_rotation(provider_id: str):
    """Reset rotation state (e.g. when connections change)."""
    _connection_rotation.pop(provider_id, None)


# ──────────────────────────────────────────────
# In-memory combo rotation state (per-process)
# ──────────────────────────────────────────────
_combo_rotation: dict[str, dict] = {}


def get_rotated_targets(
    targets: list["ResolvedTarget"],
    combo_name: str,
    strategy: str,
    sticky_limit: int = 3,
) -> list["ResolvedTarget"]:
    """Apply rotation strategy to combo targets.

    Uses random jitter (not sequential) for anti-ban.
    """
    if len(targets) <= 1 or strategy not in ("round-robin", "random"):
        return targets

    if strategy == "round-robin":
        state = _combo_rotation.get(combo_name, {"index": 0, "count": 0})

        if state["count"] < sticky_limit:
            state["count"] += 1
        else:
            state["count"] = 0
            state["index"] = random.randint(0, len(targets) - 1)

        state["index"] = state["index"] % len(targets)
        _combo_rotation[combo_name] = state

        idx = state["index"]
        return targets[idx:] + targets[:idx]

    else:  # random
        shuffled = list(targets)
        random.shuffle(shuffled)
        return shuffled


# ──────────────────────────────────────────────
# Connection cache (avoid DB query on every request)
# ──────────────────────────────────────────────
_connection_cache: dict[str, tuple[list, float]] = {}
_connection_cache_lock = asyncio.Lock()
CACHE_TTL = 30  # seconds


async def get_connections_cached(
    db: AsyncSession,
    provider_id: str,
    force_refresh: bool = False,
) -> list:
    """Get connections with caching to avoid DB query on every request."""
    now = time.time()

    if not force_refresh and provider_id in _connection_cache:
        connections, timestamp = _connection_cache[provider_id]
        if now - timestamp < CACHE_TTL:
            return connections

    # Lock around the async DB read so a concurrent call to
    # invalidate_connection_cache() cannot race the check-then-assign and
    # leave a stale snapshot in the cache (TOCTOU across the await).
    async with _connection_cache_lock:
        # Re-check inside the lock: another request may have filled it.
        if not force_refresh and provider_id in _connection_cache:
            connections, timestamp = _connection_cache[provider_id]
            if now - timestamp < CACHE_TTL:
                return connections
        result = await db.execute(
            select(ProviderConnection)
            .where(
                ProviderConnection.provider == provider_id,
                ProviderConnection.is_active == True,
            )
            .order_by(ProviderConnection.priority)
        )
        connections = result.scalars().all()
        _connection_cache[provider_id] = (connections, now)
    return connections


def invalidate_connection_cache(provider_id: str = None):
    """Invalidate connection cache."""
    # Rebuild via a fresh sync assignment (lock handled in get_connections_cached).
    if provider_id:
        _connection_cache.pop(provider_id, None)
    else:
        _connection_cache.clear()


# ──────────────────────────────────────────────
# Error rules & cooldown (from errorConfig.js)
# ──────────────────────────────────────────────

ERROR_RULES = [
    # Text-based (checked first, order = priority)
    {"text": "no credentials", "cooldown_ms": 120_000},
    {"text": "request not allowed", "cooldown_ms": 5_000},
    {"text": "improperly formed request", "cooldown_ms": 120_000},
    {"text": "rate limit", "backoff": True},
    {"text": "too many requests", "backoff": True},
    {"text": "quota exceeded", "backoff": True},
    {"text": "pricingurl", "backoff": True},
    {"text": "qoder quota/pricing", "backoff": True},
    {"text": "capacity", "backoff": True},
    {"text": "overloaded", "backoff": True},
    # Status-based (fallback when text doesn't match)
    {"status": 401, "cooldown_ms": 120_000},
    {"status": 402, "cooldown_ms": 120_000},
    {"status": 403, "cooldown_ms": 120_000},
    {"status": 404, "cooldown_ms": 120_000},
    {"status": 429, "backoff": True},
]

BACKOFF_CONFIG = {
    "base": 2_000,       # 2 seconds
    "max": 300_000,      # 5 minutes
    "max_level": 15,
}

TRANSIENT_COOLDOWN_MS = 30_000  # 30 seconds for unknown errors


def get_backoff_ms(backoff_level: int) -> int:
    """Calculate exponential backoff cooldown."""
    level = max(0, backoff_level - 1)
    cooldown = BACKOFF_CONFIG["base"] * (2 ** level)
    return min(cooldown, BACKOFF_CONFIG["max"])


def calculate_cooldown(status_code: int, error_text: str, backoff_level: int = 0) -> tuple[int, int | None]:
    """Calculate cooldown in ms. Returns (cooldown_ms, new_backoff_level | None)."""
    lower = (error_text or "").lower()

    # Text-based rules first
    for rule in ERROR_RULES:
        if "text" in rule and rule["text"] in lower:
            if rule.get("backoff"):
                new_level = min(backoff_level + 1, BACKOFF_CONFIG["max_level"])
                return get_backoff_ms(new_level), new_level
            return rule["cooldown_ms"], None

    # Status-based rules
    for rule in ERROR_RULES:
        if "status" in rule and rule["status"] == status_code:
            if rule.get("backoff"):
                new_level = min(backoff_level + 1, BACKOFF_CONFIG["max_level"])
                return get_backoff_ms(new_level), new_level
            return rule["cooldown_ms"], None

    # Default: transient cooldown
    return TRANSIENT_COOLDOWN_MS, None


def should_fallback_on_error(status_code: int, error_text: str) -> bool:
    """Check if error should trigger fallback to next connection.

    Returns True for: 5xx, 429, 401, 402, 403, 404, and text-matched errors.
    """
    if status_code >= 500:
        return True
    if status_code in (401, 402, 403, 404, 429):
        return True
    lower = (error_text or "").lower()
    for rule in ERROR_RULES:
        if "text" in rule and rule["text"] in lower:
            return True
    return False


def is_rate_limited(conn_data: dict) -> bool:
    """Check if connection is currently in cooldown."""
    until = conn_data.get("rateLimitedUntil")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def is_model_lock_active(conn_data: dict, model: str) -> bool:
    """Check if model lock on connection is still active."""
    if not model:
        return False
    lock_key = f"modelLock_{model}"
    lock_until = conn_data.get(lock_key)
    if not lock_until:
        return False
    try:
        return datetime.fromisoformat(lock_until) > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def build_cooldown_update(cooldown_ms: int, model: str = None) -> dict:
    """Build update dict for cooldown."""
    until = datetime.now(timezone.utc) + timedelta(milliseconds=cooldown_ms)
    update = {"rateLimitedUntil": until.isoformat()}
    if model:
        update[f"modelLock_{model}"] = until.isoformat()
    return update


def build_clear_cooldown_update() -> dict:
    """Build update dict to clear cooldown."""
    return {"rateLimitedUntil": None, "backoffLevel": 0}


async def mark_connection_unavailable(
    db: AsyncSession,
    connection_id: str,
    cooldown_ms: int,
    model: str = None,
    new_backoff_level: int | None = None,
    status_code: int | None = None,
    error_detail: str | None = None,
):
    """Mark connection as unavailable (write to DB only on error).

    When *new_backoff_level* is provided (from calculate_cooldown), it is used
    directly.  Otherwise we increment the current level by 1.

    When *status_code* / *error_detail* are provided they are recorded as
    errorCode / lastError in the data blob — the health contract consumed by
    provider quota trackers and the farm CLI resort tiers.
    """
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return

    data = json.loads(conn.data) if conn.data else {}
    if new_backoff_level is not None:
        backoff_level = new_backoff_level
    else:
        backoff_level = data.get("backoffLevel", 0) + 1

    update = build_cooldown_update(cooldown_ms, model)
    update["backoffLevel"] = backoff_level
    update["testStatus"] = "unavailable"
    if status_code is not None:
        update["errorCode"] = str(status_code)
    if error_detail:
        update["lastError"] = error_detail[:500]
        update["lastErrorAt"] = datetime.now(
            timezone.utc
        ).isoformat()

    data.update(update)
    conn.data = json.dumps(data)

    from app.services.connection_health import (
        resort_provider_priorities,
    )
    await resort_provider_priorities(db, conn.provider)

    await db.commit()

    # Invalidate cache for this provider
    invalidate_connection_cache(conn.provider)
    reset_connection_rotation(conn.provider)


async def clear_connection_error(db: AsyncSession, connection_id: str, model: str = None):
    """Clear connection error state (write to DB on success)."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return

    data = json.loads(conn.data) if conn.data else {}

    update = build_clear_cooldown_update()
    update["testStatus"] = "active"
    # Recovered — clear recorded upstream error state
    update["errorCode"] = None
    update["lastError"] = None
    update["lastErrorAt"] = None

    # Clear the model lock for the succeeded model
    if model:
        update[f"modelLock_{model}"] = None

    # Clear expired model locks
    now = datetime.now(timezone.utc)
    for key in list(data.keys()):
        if key.startswith("modelLock_") and key != f"modelLock_{model}":
            val = data.get(key)
            if val:
                try:
                    if datetime.fromisoformat(val) <= now:
                        update[key] = None
                except (ValueError, TypeError):
                    pass

    data.update(update)
    conn.data = json.dumps(data)

    from app.services.connection_health import (
        resort_provider_priorities,
    )
    await resort_provider_priorities(db, conn.provider)

    await db.commit()

    invalidate_connection_cache(conn.provider)


async def update_connection_usage(db: AsyncSession, connection_id: str):
    """Update lastUsedAt timestamp in connection data blob (observability)."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return

    data = json.loads(conn.data) if conn.data else {}
    data["lastUsedAt"] = datetime.now(timezone.utc).isoformat()
    conn.data = json.dumps(data)
    await db.commit()


def select_connection_for_provider(
    connections: list,
    provider_id: str,
    strategy: str = "fill-first",
    sticky_limit: int = 5,
    exclude_ids: set[str] = None,
    model: str = None,
) -> ProviderConnection | None:
    """Select ONE connection for a provider based on strategy.

    Strategies:
    - fill-first: healthy first, then priority
    - round-robin: rotate among the healthiest available
    - random: random among the healthiest available
    """
    from app.services.connection_health import (
        health_rank,
        parse_connection_data,
    )

    available: list[tuple[object, dict]] = []
    for c in connections:
        cid = str(c.id)
        if exclude_ids and cid in exclude_ids:
            continue
        conn_data = parse_connection_data(c)
        if is_rate_limited(conn_data):
            continue
        if model and is_model_lock_active(conn_data, model):
            continue
        available.append((c, conn_data))

    if not available:
        return None

    available.sort(
        key=lambda item: (
            health_rank(item[1]),
            item[0].priority or 999,
        )
    )
    best_rank = health_rank(available[0][1])
    pool = [
        c for c, data in available
        if health_rank(data) == best_rank
    ]

    if strategy == "round-robin":
        state = get_connection_rotation(provider_id)

        if state["count"] < sticky_limit:
            state["count"] += 1
        else:
            state["count"] = 0
            state["index"] = random.randint(0, len(pool) - 1)

        state["index"] = state["index"] % len(pool)
        _connection_rotation[provider_id] = state
        return pool[state["index"]]

    if strategy == "random":
        return random.choice(pool)

    return pool[0]


async def get_provider_strategy(db: AsyncSession, provider_id: str) -> tuple[str, int]:
    """Get strategy for provider (per-provider override > global default)."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()

    if row and row.data:
        data = json.loads(row.data)
        provider_strategies = data.get("providerStrategies", {})
        override = provider_strategies.get(provider_id, {})

        strategy = override.get("fallbackStrategy") or data.get("comboStrategy", "fill-first")
        sticky_limit = override.get("stickyRoundRobinLimit", 5)
        return strategy, sticky_limit

    return "fill-first", 5


def _resolve_base_url(provider: str, data: dict | None = None) -> str:
    """Resolve base URL for a provider using handler."""
    if data is None:
        data = {}

    # Try handler first — it may have region-aware URL logic
    try:
        p = Provider(provider)
        handler_url = p.resolve_base_url(data)
        if handler_url:
            return handler_url
    except (ValueError, ModuleNotFoundError):
        pass

    # Fallback to custom baseUrl from connection data
    if data.get("baseUrl"):
        return data["baseUrl"]

    # Last resort: provider config
    cfg = _get_provider_proxy_config(provider)
    return cfg.get("base_url", "")

def _build_upstream_url(provider: str, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
    """Build the upstream URL for a provider using handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
        return handler.build_upstream_url(base_url, stream, data or {}, model)
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        return f"{base_url.rstrip('/')}/chat/completions"


def _build_headers(provider: str, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
    """Build headers for upstream provider using handler."""
    try:
        p = Provider(provider)
        handler = p.handler()
        return handler.build_headers(api_key, stream, data)
    except (ValueError, ModuleNotFoundError):
        # Fallback for unknown providers
        headers = {"Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {api_key}"
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers


async def resolve_model_to_targets(
    db: AsyncSession,
    model: str,
    stream: bool = False,
    exclude_ids: set[str] = None,
    combo_strategy: str = None,
    combo_sticky_limit: int = 3,
) -> list[ResolvedTarget]:
    """Resolve a model string to one or more upstream targets.

    Resolution order:
    1. Check if model is a combo name → resolve to list of models, apply rotation
    2. Check if model is in 'provider/model' format → direct provider lookup
    3. Check provider_connections table for matching model
    4. Return empty when nothing matches (never invent a wrong provider)

    When *combo_strategy* is provided and the model is a combo, rotation is
    applied internally so callers receive already-ordered targets.
    """
    targets: list[ResolvedTarget] = []

    # 1. Check combos
    result = await db.execute(select(Combo).where(Combo.name == model))
    combo = result.scalar_one_or_none()
    if combo:
        combo_models = json.loads(combo.models) if combo.models else []
        for combo_model in combo_models:
            sub_targets = await _resolve_single_model(
                db, combo_model, stream, exclude_ids,
            )
            targets.extend(sub_targets)
        if targets and combo_strategy:
            targets = get_rotated_targets(
                targets, model, combo_strategy, combo_sticky_limit,
            )
        # Combo name matched: never fall through to bare-name lookup.
        # Empty means every member is exhausted/excluded — caller 503s.
        return targets

    # 2. Resolve single model
    return await _resolve_single_model(db, model, stream, exclude_ids)


def _conn_model_ids(conn_models: object) -> set[str]:
    """Normalize connection models blob to a set of model id strings.

    Accepts legacy ``["gpt-4"]`` lists and current
    ``[{"id": "gpt-4", "type": "llm"}]`` entries.
    """
    if not isinstance(conn_models, list):
        return set()
    ids: set[str] = set()
    for entry in conn_models:
        if isinstance(entry, str) and entry:
            ids.add(entry)
            continue
        if isinstance(entry, dict):
            mid = entry.get("id")
            if isinstance(mid, str) and mid:
                ids.add(mid)
    return ids


def _connection_has_model(
    conn_models: object, provider: str, model: str,
) -> bool:
    """True when *model* is registered on this connection."""
    ids = _conn_model_ids(conn_models)
    if model in ids:
        return True
    if f"{provider}/{model}" in ids:
        return True
    return False


async def _resolve_single_model(
    db: AsyncSession,
    model: str,
    stream: bool,
    exclude_ids: set[str] = None,
) -> list[ResolvedTarget]:
    """Resolve a single model string to upstream targets."""

    # Parse provider/model format
    if "/" in model:
        provider_name, model_name = model.split("/", 1)
        return await _build_target_for_provider(
            db, provider_name, model_name, stream, exclude_ids,
        )

    # Look through active provider connections for a match
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.is_active == True)  # noqa: E712
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()

    # Match by registered model id only. Do NOT fall back to "first
    # active connection" — that misroutes combo leftovers (e.g. grok-4.5
    # onto alims-intl / voyage / nvidia) and poisons modelLock_*.
    matches: list = []
    for conn in connections:
        cid = str(conn.id)
        if exclude_ids and cid in exclude_ids:
            continue
        data = json.loads(conn.data) if conn.data else {}
        if not _connection_has_model(
            data.get("models", []), conn.provider, model,
        ):
            continue
        matches.append(conn)

    from app.services.connection_health import (
        health_rank,
        parse_connection_data,
    )
    ranked: list = []
    for conn in matches:
        data = parse_connection_data(conn)
        if is_rate_limited(data):
            continue
        if is_model_lock_active(data, model):
            continue
        ranked.append(conn)
    ranked.sort(key=lambda c: (
        health_rank(parse_connection_data(c)),
        c.priority or 999,
    ))

    for conn in ranked:
        data = json.loads(conn.data) if conn.data else {}
        conn_api_key = data.get("apiKey", "") or data.get(
            "accessToken", "",
        )
        base_url = _resolve_base_url(conn.provider, data)
        url = _build_upstream_url(
            conn.provider, base_url, stream, data, model,
        )
        try:
            headers = _build_headers(
                conn.provider, conn_api_key, stream, data,
            )
        except ValueError:
            continue
        return [ResolvedTarget(
            url=url,
            headers=headers,
            provider=conn.provider,
            model=model,
            connection_id=str(conn.id),
        )]

    return []


async def _build_target_for_provider(
    db: AsyncSession,
    provider_name: str,
    model_name: str,
    stream: bool,
    exclude_ids: set[str] = None,
) -> list[ResolvedTarget]:
    """Build target for explicit provider/model format.

    Returns a list with at most ONE target (selected via strategy).
    Handles shared aliases (e.g. 'kilo' → kilo-gateway + kilocode) by
    trying each provider until one has active connections.
    """
    provider_ids = _resolve_provider_aliases(provider_name)

    # If not found in built-in aliases, check provider node prefixes
    if provider_ids == [provider_name]:
        import json as _json

        from app.models.provider import ProviderNode
        node_result = await db.execute(select(ProviderNode))
        for node in node_result.scalars().all():
            try:
                node_data = _json.loads(node.data) if node.data else {}
            except (_json.JSONDecodeError, TypeError):
                node_data = {}
            if node_data.get("prefix") == provider_name:
                provider_ids = [node.id]
                break

    # Try each provider for this alias until we find active connections
    for resolved_provider in provider_ids:
        connections = await get_connections_cached(db, resolved_provider)
        if not connections:
            continue

        strategy, sticky_limit = await get_provider_strategy(db, resolved_provider)

        conn = select_connection_for_provider(
            connections=list(connections),
            provider_id=resolved_provider,
            strategy=strategy,
            sticky_limit=sticky_limit,
            exclude_ids=exclude_ids,
            model=model_name,
        )

        if not conn:
            continue

        data = json.loads(conn.data) if conn.data else {}
        conn_api_key = data.get("apiKey", "") or data.get("accessToken", "")
        base_url = _resolve_base_url(resolved_provider, data)
        url = _build_upstream_url(resolved_provider, base_url, stream, data, model_name)

        try:
            headers = _build_headers(resolved_provider, conn_api_key, stream, data)
        except ValueError as e:
            logger.warning(f"Header build failed for {resolved_provider}: {e}")
            continue

        return [ResolvedTarget(
            url=url,
            headers=headers,
            provider=resolved_provider,
            model=model_name,
            connection_id=str(conn.id),
        )]

    # No matching connection found for any provider with this alias
    return []


async def get_combo_strategy(db: AsyncSession, combo_name: str = None) -> tuple[str, int]:
    """Get combo strategy. Per-combo override > global default.

    Returns (strategy, sticky_limit).
    """
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    if row and row.data:
        data = json.loads(row.data)

        # Per-combo override
        if combo_name:
            combo_strategies = data.get("comboStrategies", {})
            override = combo_strategies.get(combo_name, {})
            if override.get("fallbackStrategy"):
                return override["fallbackStrategy"], override.get("stickyRoundRobinLimit", 3)

        # Global default
        return (
            data.get("comboStrategy", "fallback"),
            data.get("stickyRoundRobinLimit", 3),
        )
    return ("fallback", 3)


# ─────────────────────────────────────────────────────────────────────────────
# TTS model string parser (used by POST /v1/audio/speech)
# ─────────────────────────────────────────────────────────────────────────────


def parse_tts_model(model_str: str) -> tuple[str, str]:
    """Parse a TTS ``model`` field into ``(tts_model, voice)``.

    The TTS endpoint requires explicit model + voice. There are **no defaults** —
    the frontend is expected to fetch the model list per provider and let the
    user pick (matches 9Router's "no hardcoded defaults — fetch from provider"
    convention used by chat and embeddings).

    By the time this parser runs the leading provider alias has already been
    stripped (caller passes only the remainder after the first ``/``).
    Supported remainder shapes:

      - ``"gpt-4o-mini-tts/alloy"``        → tts_model=gpt-4o-mini-tts, voice=alloy
      - ``"a/b/c/d"``                      → tts_model="a/b/c", voice="d"
        (everything before the *last* slash is the model, e.g. for siliconflow
        models like ``FunAudioLLM/CosyVoice2-0.5B``)

    Args:
        model_str: The remainder after the provider alias has been stripped.

    Returns:
        Tuple ``(tts_model, voice)``.

    Raises:
        ValueError: If ``model_str`` does not contain a ``/`` separating model
            from voice. Caller should map this to HTTP 400.
    """
    if not model_str:
        raise ValueError(
            "TTS model must be in 'provider/model/voice' or 'provider/voice' format — "
            "both model and voice are required (no defaults). "
            "Fetch the model list from the provider and let the user pick."
        )

    # Single segment (no slash) — treat as voice-only (e.g. edge-tts/en-US-AriaNeural)
    if "/" not in model_str:
        return model_str.strip(), model_str.strip()

    # Split on the LAST slash so multi-segment model IDs work:
    #   "FunAudioLLM/CosyVoice2-0.5B/alex" → model="FunAudioLLM/CosyVoice2-0.5B", voice="alex"
    tts_model, voice = model_str.rsplit("/", 1)
    tts_model = tts_model.strip("/")
    voice = voice.strip()

    if not tts_model or not voice:
        raise ValueError(
            "TTS model must be in 'provider/model/voice' format — "
            "neither model nor voice may be empty."
        )

    return tts_model, voice
