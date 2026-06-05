"""Core proxy service — resolve model to provider, forward request, stream response."""

import json
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.combo import Combo
from app.models.provider import ProviderConnection, ProviderNode
from app.models.settings import SettingsModel
from app.providers.provider import Provider

# ──────────────────────────────────────────────
# Frontend alias → backend provider ID mapping
# Matches the alias definitions in frontend/src/constants/providers.js
# ──────────────────────────────────────────────

ALIAS_TO_ID: dict[str, str] = {
    "kr": "kiro",
    "qw": "qwen",
    "gc": "gemini-cli",
    "if": "iflow",
    "oc": "opencode",
    "ocg": "opencode-go",
    "openrouter": "openrouter",
    "nvidia": "nvidia",
    "ollama": "ollama",
    "vx": "vertex",
    "gemini": "gemini",
    "cf": "cloudflare-ai",
    "bpm": "byteplus",
    "cc": "claude",
    "ag": "antigravity",
    "ac": "askcodi",
    "cx": "codex",
    "gh": "github",
    "cu": "cursor",
    "kc": "kilocode",
    "cl": "cline",
    "glm": "glm",
    "glm-cn": "glm-cn",
    "kimi": "kimi",
    "minimax": "minimax",
    "minimax-cn": "minimax-cn",
    "alicode": "alicode",
    "alicode-intl": "alicode-intl",
    "mimo": "xiaomi-mimo",
    "xmtp": "xiaomi-tokenplan",
    "ark": "volcengine-ark",
    "openai": "openai",
    "vag": "vercel-ai-gateway",
    "ds": "deepseek",
    "gq": "groq",
    "mi": "mistral",
    "tg": "together",
    "fw": "fireworks",
    "px": "perplexity",
    "co": "cohere",
    "cb": "cerebras",
    "hf": "huggingface",
    "sf": "siliconflow",
    "an": "anthropic",
    "az": "azure",
    "bedrock": "amazon-bedrock",
    "xai": "xai",
    "ollama-local": "ollama-local",
    "vxp": "vertex-partner",
    "vk": "volcengine",
    "tavily": "tavily",
    "brave": "brave-search",
    "serper": "serper",
    "exa": "exa",
    "fal": "fal-ai",
    "stability": "stability-ai",
    "jina": "jina-ai",
    "gw": "grok-web",
    "pw": "perplexity-web",
    "nanobanana": "nanobanana",
    "chutes": "chutes",
    "assemblyai": "assemblyai",
    "kg": "kilo-gateway",
    "qd": "qoder",
}


def _resolve_provider_alias(provider_name: str) -> str:
    """Resolve a frontend provider alias to the backend provider ID.

    The frontend sends model strings like "an/claude-3-5-sonnet" where "an"
    is the storage alias for "anthropic". This function resolves the alias
    to the actual provider ID used in ProviderConnection.provider.
    """
    return ALIAS_TO_ID.get(provider_name, provider_name)

# Reverse mapping: provider ID → alias
ID_TO_ALIAS: dict[str, str] = {v: k for k, v in ALIAS_TO_ID.items()}

# ──────────────────────────────────────────────
# Provider URL/header configuration
# ──────────────────────────────────────────────

def _get_provider_proxy_config(provider: str) -> dict:
    """Get provider proxy config from Provider class.

    Returns dict with keys: base_url, format, auth_header, auth_prefix, extra_headers.
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
):
    """Mark connection as unavailable (write to DB only on error).

    When *new_backoff_level* is provided (from calculate_cooldown), it is used
    directly.  Otherwise we increment the current level by 1.
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

    data.update(update)
    conn.data = json.dumps(data)
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
    - fill-first: priority highest (default)
    - round-robin: rotate with random jitter (anti-ban)
    - random: random selection each request
    """
    available = []
    for c in connections:
        cid = str(c.id)
        if exclude_ids and cid in exclude_ids:
            continue
        conn_data = json.loads(c.data) if c.data else {}
        if is_rate_limited(conn_data):
            continue
        if model and is_model_lock_active(conn_data, model):
            continue
        available.append(c)

    if not available:
        return None

    # Sort by priority for fill-first fallback
    available.sort(key=lambda c: c.priority or 999)

    if strategy == "round-robin":
        state = get_connection_rotation(provider_id)

        if state["count"] < sticky_limit:
            state["count"] += 1
        else:
            state["count"] = 0
            state["index"] = random.randint(0, len(available) - 1)

        state["index"] = state["index"] % len(available)
        _connection_rotation[provider_id] = state
        return available[state["index"]]

    elif strategy == "random":
        return random.choice(available)

    else:  # fill-first
        return available[0]


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
    """Resolve base URL for a provider, handling region-specific URLs."""
    if data is None:
        data = {}

    # Handle region-specific providers (region takes precedence over stored baseUrl)
    if provider == "xiaomi-tokenplan":
        region = data.get("region", "sgp")
        region_urls = {
            "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
            "cn": "https://token-plan-cn.xiaomimimo.com/v1",
            "ams": "https://token-plan-ams.xiaomimimo.com/v1",
        }
        return region_urls.get(region, region_urls["sgp"])

    # Check if custom baseUrl is provided in connection data
    if data.get("baseUrl"):
        return data["baseUrl"]

    # Fallback to provider config
    cfg = _get_provider_proxy_config(provider)
    return cfg.get("base_url", "")

def _build_upstream_url(provider: str, base_url: str, stream: bool = False, data: dict | None = None, model: str = "") -> str:
    """Build the upstream URL for a provider."""
    cfg = _get_provider_proxy_config(provider)
    fmt = cfg["format"]
    base = base_url.rstrip("/")
    if data is None:
        data = {}

    if fmt == "claude":
        return f"{base}/messages"
    elif fmt == "gemini":
        action = "streamGenerateContent?alt=sse" if stream else "generateContent"
        model_id = model.replace("models/", "") if model else ""
        return f"{base}/models/{model_id}:{action}" if model_id else f"{base}/models"
    elif fmt == "azure":
        endpoint = data.get("azureEndpoint") or base
        deployment = data.get("deployment", "gpt-4")
        api_version = data.get("apiVersion", "2024-10-01-preview")
        return f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    elif provider == "cloudflare-ai":
        account_id = data.get("accountId", "")
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
    elif provider == "qoder":
        # Qoder uses COSY-signed endpoint with Encode=1
        return f"{base}/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1"
    else:
        return f"{base}/chat/completions"


def _build_headers(provider: str, api_key: str, stream: bool = False, data: dict | None = None) -> dict[str, str]:
    """Build headers for upstream provider."""
    if not api_key:
        raise ValueError(f"No API key configured for provider \"{provider}\"")

    # ── Qoder: COSY-signed headers ──────────────────────────────────────────
    # Note: For Qoder, headers are built with empty body here.
    # The actual COSY signing with body happens in build_qoder_request().
    if provider == "qoder":
        from app.services.qoder.cosy import build_cosy_headers
        from app.services.qoder.constants import QODER_CHAT_URL_ENCODED

        psd = data or {}
        user_id = psd.get("userId", "")
        machine_id = psd.get("machineId", "")

        if not user_id:
            raise ValueError("Qoder userId missing — cannot build COSY headers")

        # Build COSY headers with empty body - will be re-signed later
        cosy_headers = build_cosy_headers(
            body=b"",
            request_url=QODER_CHAT_URL_ENCODED,
            user_id=user_id,
            auth_token=api_key,
            name=psd.get("displayName", ""),
            email=psd.get("email", ""),
            machine_id=machine_id,
        )

        if stream:
            cosy_headers["Accept"] = "text/event-stream"

        return cosy_headers

    # ── Standard providers ──────────────────────────────────────────────────
    cfg = _get_provider_proxy_config(provider)
    headers = {"Content-Type": "application/json"}

    # Auth header
    headers[cfg["auth_header"]] = f"{cfg['auth_prefix']}{api_key}"

    # Extra provider-specific headers
    if "extra_headers" in cfg:
        headers.update(cfg["extra_headers"])

    if stream:
        headers["Accept"] = "text/event-stream"

    return headers


async def build_qoder_request(
    target: ResolvedTarget,
    body: dict,
    data: dict,
) -> tuple[bytes, dict[str, str]]:
    """Build a Qoder-specific request with COSY signing.

    Args:
        target: Resolved target with URL and headers
        body: Original OpenAI-format request body
        data: Connection data (with userId, machineId, etc.)

    Returns:
        (encoded_body_bytes, signed_headers) tuple
    """
    from app.services.qoder.transform import build_qoder_request_body
    from app.services.qoder.cosy import build_cosy_headers
    from app.services.qoder.constants import QODER_CHAT_URL_ENCODED
    from app.services.qoder.models import get_qoder_model_config
    from app.services.qoder.encoding import qoder_encode_body

    user_id = data.get("userId", "")
    machine_id = data.get("machineId", "")
    access_token = data.get("accessToken", "")
    model = body.get("model", "")

    # Get model config from cache — if missing, force-refresh catalog first
    # Resolve model ID: "qd/qoder/auto" → alias "qd" resolves to "qoder" → strip → "auto"
    if "/" in model:
        parts = model.split("/", 1)
        resolved = ALIAS_TO_ID.get(parts[0], parts[0])
        remainder = parts[1]
        qoder_key = remainder[len(resolved) + 1:] if remainder.startswith(resolved + "/") else remainder
    else:
        qoder_key = model
    model_config = get_qoder_model_config(user_id, access_token, qoder_key)
    if model_config is None:
        from app.services.qoder.models import resolve_qoder_models
        credentials = {
            "access_token": access_token,
            "provider_specific": {"userId": user_id, "machineId": machine_id},
        }
        await resolve_qoder_models(credentials, force_refresh=True)
        model_config = get_qoder_model_config(user_id, access_token, qoder_key)

    # Build Qoder-format request body
    qoder_body = build_qoder_request_body(
        model=model,
        body=body,
        credentials={"provider_specific": {"userId": user_id, "machineId": machine_id}},
        model_config=model_config,
        qoder_key=qoder_key,
    )

    # JSON → WAF-bypass encode (matching Node.js: JSON.stringify → qoderEncodeBody)
    plain_bytes = json.dumps(qoder_body).encode("utf-8")
    encoded_str = qoder_encode_body(plain_bytes)
    encoded_bytes = encoded_str.encode("latin1")

    # Build COSY headers with the ENCODED body (not plain JSON)
    cosy_headers = build_cosy_headers(
        body=encoded_bytes,
        request_url=QODER_CHAT_URL_ENCODED,
        user_id=user_id,
        auth_token=access_token,
        name=data.get("displayName", ""),
        email=data.get("email", ""),
        machine_id=machine_id,
    )

    # Add headers that Node.js executor sets separately (not in cosy.js)
    model_source = (model_config or {}).get("source", "system")
    cosy_headers["X-Model-Key"] = qoder_key
    cosy_headers["X-Model-Source"] = model_source
    cosy_headers["Cache-Control"] = "no-cache"
    cosy_headers["Accept"] = "text/event-stream"

    return encoded_bytes, cosy_headers


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
    4. Fall back to openai provider with the model name as-is

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
            sub_targets = await _resolve_single_model(db, combo_model, stream, exclude_ids)
            targets.extend(sub_targets)
        if targets and combo_strategy:
            targets = get_rotated_targets(targets, model, combo_strategy, combo_sticky_limit)
        if targets:
            return targets

    # 2. Resolve single model
    targets = await _resolve_single_model(db, model, stream, exclude_ids)
    return targets


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
        return await _build_target_for_provider(db, provider_name, model_name, stream, exclude_ids)

    # Look through active provider connections for a match
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()

    # Check provider nodes
    node_result = await db.execute(select(ProviderNode))
    nodes = {n.id: n for n in node_result.scalars().all()}

    # Try to find a connection whose provider supports this model
    # First pass: check if any connection has this model registered
    for conn in connections:
        data = json.loads(conn.data) if conn.data else {}
        conn_models = data.get("models", [])
        # Check both exact match and provider-prefixed match
        model_match = model in conn_models or f"{conn.provider}/{model}" in conn_models
        if model_match:
            conn_api_key = data.get("apiKey", "") or data.get("accessToken", "")
            base_url = _resolve_base_url(conn.provider, data)
            url = _build_upstream_url(conn.provider, base_url, stream, data, model)
            try:
                headers = _build_headers(conn.provider, conn_api_key, stream, data)
            except ValueError:
                continue
            return [ResolvedTarget(
                url=url,
                headers=headers,
                provider=conn.provider,
                model=model,
                connection_id=str(conn.id),
            )]

    # Second pass: no model match found, fall back to first active connection
    for conn in connections:
        data = json.loads(conn.data) if conn.data else {}
        conn_api_key = data.get("apiKey", "") or data.get("accessToken", "")
        base_url = _resolve_base_url(conn.provider, data)
        url = _build_upstream_url(conn.provider, base_url, stream, data, model)
        try:
            headers = _build_headers(conn.provider, conn_api_key, stream, data)
        except ValueError:
            continue
        return [ResolvedTarget(
            url=url,
            headers=headers,
            provider=conn.provider,
            model=model,
            connection_id=str(conn.id),
        )]

    # Default: no matching connection found — return empty so caller can give a meaningful error
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
    """
    resolved_provider = _resolve_provider_alias(provider_name)

    connections = await get_connections_cached(db, resolved_provider)
    if not connections:
        return []

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
        return []

    data = json.loads(conn.data) if conn.data else {}
    conn_api_key = data.get("apiKey", "") or data.get("accessToken", "")
    base_url = _resolve_base_url(resolved_provider, data)
    url = _build_upstream_url(resolved_provider, base_url, stream, data, model_name)

    try:
        headers = _build_headers(resolved_provider, conn_api_key, stream, data)
    except ValueError:
        return []

    return [ResolvedTarget(
        url=url,
        headers=headers,
        provider=resolved_provider,
        model=model_name,
        connection_id=str(conn.id),
    )]


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
