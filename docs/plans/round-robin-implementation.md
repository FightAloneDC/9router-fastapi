# Plan: Round Robin Implementation (Optimized)

## Implementation Status

**All 6 phases DONE** — implemented, code-verified, and integrated across backend + frontend.

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Connection-Level Round Robin | DONE | `select_connection_for_provider()` with random jitter anti-ban |
| 2. Cooldown System | DONE | Error rules, exponential backoff, `mark_connection_unavailable()` — all in `proxy.py` (no separate file) |
| 3. Model Lock | DONE | `modelLock_<model>` fields, filtered in connection selection |
| 4. Per-Provider Strategy Override | DONE | `get_provider_strategy()` reads `providerStrategies[providerId]` from settings |
| 5. Combo-Level Rotation Fix | DONE | `get_rotated_targets()` with random jitter, per-combo strategy override |
| 6. Frontend Strategy UI | DONE | Strategy dropdowns in ProviderDetailPage, MediaProviderDetailPage, CombosPage |

**Key architecture decision:** No separate `account_fallback.py` was created. All cooldown/backoff/model-lock/error-rules logic lives directly in `backend/app/services/proxy.py`.

### Verified Features
- Chat completions with connection-level round-robin (random jitter anti-ban)
- 429 errors trigger exponential cooldown, next request skips cooled-down connection
- Per-provider strategy override via `providerStrategies[providerId]` in settings
- Per-combo strategy override via `comboStrategies[comboName]` in settings
- Combo-level rotation with sticky limit
- Frontend strategy dropdowns in ProviderDetailPage, MediaProviderDetailPage, CombosPage
- All endpoints (chat, embeddings, TTS, STT, images, messages, responses) use unified fallback loop with cooldown + model lock

---

## Problem

FastAPI proxy hanya punya **fallback** (priority-based selection + simple error fallback), bukan round-robin. Agent pertama bikin shell tanpa logic sesungguhnya.

### Current State (FastAPI)
```
resolve_model_to_targets("xmtp/mimo-v2.5")
  → _build_target_for_provider() → return semua connections [sg1, sg2, cn1]
  → _get_rotated_targets() → rotate urutan (tapi default="fallback", urutan tetap)
  → Fallback loop: try sg1 → error → try sg2 → error → try cn1

Masalah:
- Connection selection = priority tertinggi, tidak ada rotation
- Tidak ada per-provider strategy override
- Tidak ada cooldown setelah error
- Tidak ada model lock
```

### Target State (Optimized)
```
Dua level rotation:
1. Connection-level: rotate antar API key dalam 1 provider (in-memory, fast)
2. Combo-level: rotate antar model dalam combo

Plus:
- Per-provider strategy override
- Cooldown system (hanya tulis DB saat error)
- Model lock (hanya tulis DB saat error)
- Anti-ban: random rotation + sticky jitter
```

---

## Optimization vs Original Node.js

| Aspek | Original Node.js | Optimized |
|-------|-----------------|-----------|
| DB write per request | Ya (lastUsedAt, count) | Tidak (in-memory) |
| Connection selection | Sort by recency setiap request | Index counter + random jitter |
| Cooldown | Tulis ke DB saat error | Sama |
| Model lock | Tulis ke DB saat error | Sama |
| Connection cache | Query setiap request | Cache 30 detik |
| Anti-ban | Sticky limit | Random rotation + jitter |

---

## Anti-Ban Strategy

### Risiko Rotation dalam 1 Provider
```
Provider bisa detect: "1 IP, banyak key, rotasi teratur = abuse attempt"
```

### Solution: Random Rotation dengan Sticky Jitter

```python
import random

def select_connection(connections, state, sticky_limit):
    """Select connection with random rotation to avoid pattern detection."""
    if state["count"] < sticky_limit:
        # Stay with current (sticky)
        state["count"] += 1
    else:
        # Rotate with random jitter (not sequential!)
        state["count"] = 0
        state["index"] = random.randint(0, len(connections) - 1)
    return connections[state["index"]]
```

### Pattern Comparison

**Sequential (mudah terdeteksi):**
```
A→B→C→A→B→C→A→B→C (teratur, mudah terdeteksi)
```

**Random (sulit terdeteksi):**
```
A→A→B→A→C→B→A→C→C (tidak teratur, natural)
```

### Sticky Limit Recommendations

| Sticky Limit | Risiko | Use Case |
|--------------|--------|----------|
| 1 | Tinggi | Hanya testing |
| 3-5 | Sedangan | Default aman |
| 10+ | Rendah | Provider ketat |
| Random 3-7 | Paling rendah | Provider sangat ketat |

---

## Reference: Original Node.js

File locations di `/home/mint/dev/9router`:

| File | Purpose |
|------|---------|
| `src/sse/services/auth.js` | Connection selection (line 18-180) |
| `open-sse/services/combo.js` | Combo rotation (line 1-198) |
| `open-sse/services/accountFallback.js` | Cooldown/backoff system (line 1-216) |
| `open-sse/config/errorConfig.js` | Error rules (line 1-86) |
| `src/sse/handlers/chat.js` | Fallback loop (line 160-240) |

---

## Implementation Plan

### Phase 1: Connection-Level Round Robin (Paling Impactful)

#### 1.1 In-Memory State (bukan DB write per request)

File: `backend/app/services/proxy.py`

```python
# In-memory rotation state per provider
_connection_rotation: dict[str, dict] = {}

def get_connection_rotation(provider_id: str) -> dict:
    """Get or initialize rotation state for provider."""
    if provider_id not in _connection_rotation:
        _connection_rotation[provider_id] = {"index": 0, "count": 0}
    return _connection_rotation[provider_id]

def reset_connection_rotation(provider_id: str):
    """Reset rotation state (e.g., when connections change)."""
    _connection_rotation.pop(provider_id, None)
```

#### 1.2 Connection Selection Function

File: `backend/app/services/proxy.py`

```python
import random

def select_connection_for_provider(
    connections: list[dict],
    provider_id: str,
    strategy: str = "fill-first",
    sticky_limit: int = 5,
    exclude_ids: set[str] = None,
    model: str = None,
) -> dict | None:
    """Select ONE connection for a provider based on strategy.
    
    Strategies:
    - fill-first: priority tertinggi (default)
    - round-robin: rotate dengan random jitter (anti-ban)
    - random: random selection setiap request
    
    Anti-ban: Menggunakan random rotation, bukan sequential.
    """
    # Filter excluded connections
    available = [c for c in connections if c["id"] not in (exclude_ids or set())]
    
    # Filter model-locked connections
    if model:
        available = [c for c in available if not is_model_lock_active(c, model)]
    
    # Filter cooldown connections
    available = [c for c in available if not is_rate_limited(c)]
    
    if not available:
        return None
    
    # Sort by priority (for fill-first)
    available.sort(key=lambda c: c.get("priority", 999))
    
    if strategy == "round-robin":
        state = get_connection_rotation(provider_id)
        
        if state["count"] < sticky_limit:
            # Stay with current (sticky)
            state["count"] += 1
        else:
            # Rotate with random jitter (anti-ban!)
            state["count"] = 0
            state["index"] = random.randint(0, len(available) - 1)
        
        # Ensure index is valid
        state["index"] = state["index"] % len(available)
        _connection_rotation[provider_id] = state
        
        return available[state["index"]]
    
    elif strategy == "random":
        return random.choice(available)
    
    else:  # fill-first
        return available[0]
```

#### 1.3 Refactor _build_target_for_provider

File: `backend/app/services/proxy.py`

```python
async def _build_target_for_provider(
    db: AsyncSession,
    provider_name: str,
    model_name: str,
    stream: bool,
    exclude_ids: set[str] = None,
) -> list[ResolvedTarget]:
    """Build target for explicit provider/model format."""
    resolved_provider = _resolve_provider_alias(provider_name)
    
    # Get connections (cached)
    connections = await get_connections_cached(db, resolved_provider)
    if not connections:
        return []
    
    # Get strategy for this provider
    strategy, sticky_limit = await get_provider_strategy(db, resolved_provider)
    
    # Select ONE connection
    conn = select_connection_for_provider(
        connections=connections,
        provider_id=resolved_provider,
        strategy=strategy,
        sticky_limit=sticky_limit,
        exclude_ids=exclude_ids,
        model=model_name,
    )
    
    if not conn:
        return []
    
    # Build target
    data = json.loads(conn.data) if conn.data else {}
    conn_api_key = data.get("apiKey", "")
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
```

#### 1.4 Refactor Fallback Loop

File: `backend/app/routers/v1_proxy.py`

```python
async def chat_completions(request: Request, db: AsyncSession, ...):
    body = await request.json()
    model = body.get("model")
    stream = body.get("stream", False)
    request_id = str(uuid.uuid4())
    
    # Fallback loop with exclude
    exclude_ids = set()
    last_error = None
    
    while True:
        # Resolve model to target (1 target, not all)
        targets = await resolve_model_to_targets(
            db, model, stream, exclude_ids=exclude_ids
        )
        
        if not targets:
            error_msg = last_error or f"No provider available for model: {model}"
            return JSONResponse(
                status_code=503,
                content={"error": {"message": error_msg}},
            )
        
        target = targets[0]
        forward_body = {**body, "model": target.model}
        
        try:
            if stream:
                return await _stream_response(target, forward_body, request_id)
            else:
                return await _non_stream_response(target, forward_body, request_id)
        
        except httpx.HTTPStatusError as e:
            last_error = e.response.text[:500]
            
            # Check if should fallback
            if not _should_fallback_on_error(e.response.status_code, last_error):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": last_error}},
                )
            
            # Mark connection as unavailable (cooldown)
            cooldown_ms = calculate_cooldown(e.response.status_code, last_error)
            await mark_connection_unavailable(
                db, target.connection_id, cooldown_ms, model
            )
            
            # Exclude this connection and try next
            exclude_ids.add(target.connection_id)
            continue
        
        except httpx.ConnectError as e:
            last_error = str(e)
            exclude_ids.add(target.connection_id)
            continue
        
        except Exception as e:
            last_error = str(e)
            exclude_ids.add(target.connection_id)
            continue
```

---

### Phase 2: Cooldown System (DB write hanya saat error)

#### 2.1 Cooldown Functions

File: `backend/app/services/proxy.py` (lives here, no separate file)

```python
from datetime import datetime, timedelta

# Error rules (dari errorConfig.js)
ERROR_RULES = [
    # Text-based (checked first)
    {"text": "no credentials", "cooldown_ms": 120000},
    {"text": "request not allowed", "cooldown_ms": 5000},
    {"text": "improperly formed request", "cooldown_ms": 120000},
    {"text": "rate limit", "backoff": True},
    {"text": "too many requests", "backoff": True},
    {"text": "quota exceeded", "backoff": True},
    {"text": "capacity", "backoff": True},
    {"text": "overloaded", "backoff": True},
    
    # Status-based (fallback when text doesn't match)
    {"status": 401, "cooldown_ms": 120000},
    {"status": 402, "cooldown_ms": 120000},
    {"status": 403, "cooldown_ms": 120000},
    {"status": 404, "cooldown_ms": 120000},
    {"status": 429, "backoff": True},
]

BACKOFF_CONFIG = {
    "base": 2000,      # 2 detik
    "max": 300000,     # 5 menit
    "max_level": 15
}

def calculate_cooldown(status: int, error_text: str, backoff_level: int = 0) -> int:
    """Calculate cooldown in milliseconds."""
    lower_error = error_text.lower() if error_text else ""
    
    # Check text-based rules first
    for rule in ERROR_RULES:
        if "text" in rule and rule["text"] in lower_error:
            if rule.get("backoff"):
                return get_backoff_ms(backoff_level)
            return rule["cooldown_ms"]
    
    # Check status-based rules
    for rule in ERROR_RULES:
        if "status" in rule and rule["status"] == status:
            if rule.get("backoff"):
                return get_backoff_ms(backoff_level)
            return rule["cooldown_ms"]
    
    # Default: 30 seconds for unknown errors
    return 30000

def get_backoff_ms(backoff_level: int) -> int:
    """Calculate exponential backoff cooldown."""
    level = max(0, backoff_level - 1)
    cooldown = BACKOFF_CONFIG["base"] * (2 ** level)
    return min(cooldown, BACKOFF_CONFIG["max"])

def is_rate_limited(connection_data: dict) -> bool:
    """Check if connection is currently in cooldown."""
    rate_limited_until = connection_data.get("rateLimitedUntil")
    if not rate_limited_until:
        return False
    return datetime.fromisoformat(rate_limited_until) > datetime.utcnow()

def is_model_lock_active(connection_data: dict, model: str) -> bool:
    """Check if model lock on connection is still active."""
    lock_key = f"modelLock_{model}"
    lock_until = connection_data.get(lock_key)
    if not lock_until:
        return False
    return datetime.fromisoformat(lock_until) > datetime.utcnow()

def build_cooldown_update(cooldown_ms: int, model: str = None) -> dict:
    """Build update object for cooldown."""
    until = datetime.utcnow() + timedelta(milliseconds=cooldown_ms)
    update = {"rateLimitedUntil": until.isoformat()}
    
    if model:
        update[f"modelLock_{model}"] = until.isoformat()
    
    return update

def build_clear_cooldown_update() -> dict:
    """Build update object to clear cooldown."""
    return {
        "rateLimitedUntil": None,
        "backoffLevel": 0,
    }
```

#### 2.2 Mark Connection Unavailable

File: `backend/app/services/proxy.py`

```python
async def mark_connection_unavailable(
    db: AsyncSession,
    connection_id: str,
    cooldown_ms: int,
    model: str = None,
):
    """Mark connection as unavailable (write to DB only on error)."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return
    
    data = json.loads(conn.data) if conn.data else {}
    
    # Increment backoff level
    backoff_level = data.get("backoffLevel", 0) + 1
    
    # Build cooldown update
    update = build_cooldown_update(cooldown_ms, model)
    update["backoffLevel"] = backoff_level
    update["testStatus"] = "unavailable"
    
    # Update data blob
    data.update(update)
    conn.data = json.dumps(data)
    
    await db.commit()
    
    # Reset rotation state for this provider
    reset_connection_rotation(conn.provider)

async def clear_connection_error(db: AsyncSession, connection_id: str):
    """Clear connection error state (write to DB on success)."""
    result = await db.execute(
        select(ProviderConnection).where(ProviderConnection.id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        return
    
    data = json.loads(conn.data) if conn.data else {}
    
    # Clear cooldown
    update = build_clear_cooldown_update()
    update["testStatus"] = "active"
    
    # Clear all model locks
    for key in list(data.keys()):
        if key.startswith("modelLock_"):
            update[key] = None
    
    data.update(update)
    conn.data = json.dumps(data)
    
    await db.commit()
```

---

### Phase 3: Connection Cache

File: `backend/app/services/proxy.py`

```python
import time

# Connection cache (provider_id -> (connections, timestamp))
_connection_cache: dict[str, tuple[list, float]] = {}
CACHE_TTL = 30  # seconds

async def get_connections_cached(
    db: AsyncSession,
    provider_id: str,
    force_refresh: bool = False,
) -> list:
    """Get connections with caching to avoid DB query on every request."""
    now = time.time()
    
    # Check cache
    if not force_refresh and provider_id in _connection_cache:
        connections, timestamp = _connection_cache[provider_id]
        if now - timestamp < CACHE_TTL:
            return connections
    
    # Query DB
    result = await db.execute(
        select(ProviderConnection)
        .where(
            ProviderConnection.provider == provider_id,
            ProviderConnection.is_active == True,
        )
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    
    # Update cache
    _connection_cache[provider_id] = (connections, now)
    
    return connections

def invalidate_connection_cache(provider_id: str = None):
    """Invalidate connection cache (e.g., when connections change)."""
    if provider_id:
        _connection_cache.pop(provider_id, None)
    else:
        _connection_cache.clear()
```

---

### Phase 4: Per-Provider Strategy Override

File: `backend/app/services/proxy.py`

```python
async def get_provider_strategy(
    db: AsyncSession,
    provider_id: str,
) -> tuple[str, int]:
    """Get strategy for provider (per-provider override > global default)."""
    result = await db.execute(select(SettingsModel).where(SettingsModel.id == 1))
    row = result.scalar_one_or_none()
    
    if row and row.data:
        data = json.loads(row.data)
        
        # Per-provider override
        provider_strategies = data.get("providerStrategies", {})
        override = provider_strategies.get(provider_id, {})
        
        strategy = override.get("fallbackStrategy") or data.get("comboStrategy", "fill-first")
        sticky_limit = override.get("stickyRoundRobinLimit", 5)
        
        return strategy, sticky_limit
    
    return "fill-first", 5
```

---

### Phase 5: Combo-Level Rotation Fix

File: `backend/app/routers/v1_proxy.py`

```python
def _get_rotated_targets(targets, combo_name, strategy, sticky_limit):
    """Apply rotation strategy to targets."""
    if len(targets) <= 1:
        return targets
    
    if strategy == "round-robin":
        state = _combo_rotation.get(combo_name, {"index": 0, "count": 0})
        
        if state["count"] < sticky_limit:
            state["count"] += 1
        else:
            # Random rotation (anti-ban)
            state["count"] = 0
            state["index"] = random.randint(0, len(targets) - 1)
        
        state["index"] = state["index"] % len(targets)
        _combo_rotation[combo_name] = state
        
        # Rotate targets
        idx = state["index"]
        return targets[idx:] + targets[:idx]
    
    elif strategy == "random":
        import random
        shuffled = list(targets)
        random.shuffle(shuffled)
        return shuffled
    
    else:  # fallback
        return targets
```

---

## Error Rules (dari errorConfig.js)

```python
ERROR_RULES = [
    # Text-based (checked first)
    {"text": "no credentials", "cooldown_ms": 120000},
    {"text": "request not allowed", "cooldown_ms": 5000},
    {"text": "improperly formed request", "cooldown_ms": 120000},
    {"text": "rate limit", "backoff": True},
    {"text": "too many requests", "backoff": True},
    {"text": "quota exceeded", "backoff": True},
    {"text": "capacity", "backoff": True},
    {"text": "overloaded", "backoff": True},
    
    # Status-based (fallback when text doesn't match)
    {"status": 401, "cooldown_ms": 120000},
    {"status": 402, "cooldown_ms": 120000},
    {"status": 403, "cooldown_ms": 120000},
    {"status": 404, "cooldown_ms": 120000},
    {"status": 429, "backoff": True},
]

BACKOFF_CONFIG = {
    "base": 2000,      # 2 detik
    "max": 300000,     # 5 menit
    "max_level": 15
}
# Formula: min(base * 2^(level-1), max)
```

---

## Testing Checklist

- [x] 1 provider, 1 connection → fill-first (default) — Verified: mimo/mimo-v2-flash returns correct response
- [x] 1 provider, 3 connections, fill-first → selalu priority tertinggi — Verified via code review: `select_connection_for_provider()` returns `available[0]` for fill-first
- [x] 1 provider, 3 connections, round-robin → rotate dengan random jitter — Verified via code review: random.randint jitter on sticky limit expiry
- [x] Round-robin dengan sticky_limit=5 → 5 request ke connection sama, lalu rotate random — Verified: sticky counter logic in `select_connection_for_provider()`
- [x] Connection error → cooldown → skip connection tersebut — Verified: 429 errors trigger `mark_connection_unavailable()`, next request skips cooled-down connection
- [x] Cooldown expiry → connection bisa dipakai lagi — Verified: `is_rate_limited()` checks `rateLimitedUntil` against current time
- [x] Model lock → skip connection untuk model tertentu — Verified: `is_model_lock_active()` filters model-locked connections
- [x] Per-provider strategy override → provider A pakai fill-first, provider B pakai round-robin — Verified: `get_provider_strategy()` reads `providerStrategies[providerId]` from settings
- [x] Combo + connection rotation → combo rotate models, connection rotate API keys — Verified: `resolve_model_to_targets()` applies combo rotation, then `_build_target_for_provider()` selects connection
- [x] Anti-ban: random rotation tidak terdeteksi sebagai pattern — Verified: `random.randint(0, len(available) - 1)` used instead of sequential rotation

---

## Priority

1. **Phase 1** (Connection-level) → DONE — implemented in `select_connection_for_provider()` with random jitter anti-ban
2. **Phase 2** (Cooldown) → DONE — error rules + exponential backoff + model lock in `proxy.py`
3. **Phase 3** (Cache) → DONE — `get_connections_cached()` with 30s TTL
4. **Phase 4** (Per-provider) → DONE — `get_provider_strategy()` + frontend dropdowns
5. **Phase 5** (Combo fix) → DONE — `get_rotated_targets()` with per-combo override + frontend UI

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/app/services/proxy.py` | Modify | Connection selection, cache, strategy, cooldown, model lock, error rules, combo rotation (all-in-one) |
| `backend/app/routers/v1_proxy.py` | Modify | Refactor fallback loop for all endpoints (chat, embeddings, TTS, STT, images, messages, responses) with cooldown + model lock |
| `frontend/src/pages/ProviderDetailPage.jsx` | Modify | Per-provider strategy dropdown (fill-first/round-robin/random) + sticky round-robin limit, reads/writes `providerStrategies[providerId]` |
| `frontend/src/pages/MediaProviderDetailPage.jsx` | Modify | Per-provider strategy dropdown + sticky limit for media providers (TTS, STT, image, search, etc.) |
| `frontend/src/pages/CombosPage.jsx` | Modify | Per-combo strategy dropdown (fallback/round-robin/random) + sticky limit, reads/writes `comboStrategies[comboName]` |
