# Qoder Bug: Model Test Fails After Switching Connection (Stale Cache)

> **Status:** Fixed  
> **Date:** 2026-06-09  
> **Related file:** `backend/app/routers/providers/connections.py`  
> **Severity:** High — all providers affected, not just Qoder

---

## 1. Symptoms

User reported the following pattern on `/providers/qoder` page:

1. Test model `qmodel_latest` via button on connection A → **success**
2. Disable connection A, enable connection B → test model → **error "Login expired"**
3. Switch back to connection A (disable B, enable A) → test model → **error "Login expired"**
4. Backend test via direct API (`POST /providers/{id}/test`) → **success** (token valid)

Token in DB never expired. "Login expired" error only appeared in UI/frontend
after connection switch operations.

---

## 2. Root Cause

### Connection Cache Not Invalidated

`update_provider()` (PATCH `/providers/{id}`) updates `is_active` in DB
but **did not call `invalidate_connection_cache()`**.

Proxy service uses in-memory cache with 30-second TTL:

```python
# backend/app/services/proxy.py
_connection_cache: dict[str, tuple[list, float]] = {}
CACHE_TTL = 30  # seconds

async def get_connections_cached(db, provider_id, force_refresh=False):
    now = time.time()
    if not force_refresh and provider_id in _connection_cache:
        connections, timestamp = _connection_cache[provider_id]
        if now - timestamp < CACHE_TTL:
            return connections  # ← STALE DATA
    # ... fresh DB query
```

Cache was only invalidated in 2 places:
- `set_connection_error()` — when connection error is recorded
- `clear_connection_error()` — when connection error is cleared

Not in `update_provider()`.

### Impact on Model Test

Model test flow (`POST /models/test`):

```
Frontend → POST /models/test { model: "qd/qoder/qmodel_latest" }
  → resolve_model_to_targets()
    → _build_target_for_provider()
      → get_connections_cached("qoder")  ← STALE CACHE
        → select_connection_for_provider()  ← selects from old data
```

After user disables A and enables B:
- Cache still thinks A is active, B is not active
- Model test may incorrectly resolve to disabled connection
- Or not find any connection at all (if B is not yet cached)

### Why "Login expired"?

Qoder returns error `{"code":"105","message":"Login expired"}` (HTTP 403)
when COSY-signed request uses an invalid token or connection that is
no longer active on Qoder's side.

This error appeared because model test incorrectly resolved to a connection
whose token had expired in upstream Qoder (not in our DB).

---

## 3. Investigation Steps

### 3.1 Verify Token Still Valid

```bash
# Test userinfo directly
curl -s "https://openapi.qoder.sh/api/v1/userinfo" \
  -H "Authorization: Bearer jt-JSbNAAWAsAGziAm4TAd3DIes"
# Result: HTTP 200, full user info

# Test COSY-signed model list
# (via backend python script with build_cosy_headers)
# Result: HTTP 200, 11 models
```

### 3.2 Verify DB State

```sql
SELECT id, name, test_status,
  LEFT(data::jsonb->>'accessToken', 20) as token_prefix,
  data::jsonb->>'lastError' as last_error
FROM provider_connections WHERE provider = 'qoder';
-- All connections: test_status='connected', last_error=NULL
```

### 3.3 Verify Backend Test Endpoint

```bash
curl -X POST "http://localhost:9000/providers/{id}/test" \
  -H "Authorization: Bearer $TOKEN"
# Result: {"valid": true, "latencyMs": 141}
```

### 3.4 Trace Proxy Resolution Path

```bash
# Check where invalidate_connection_cache is called
grep -rn "invalidate_connection_cache" backend/app/ --include="*.py"
# Result: only in set_connection_error and clear_connection_error
# NOT in update_provider
```

### 3.5 Reproduce Bug

```bash
# Disable connection
curl -X PATCH "/providers/{id}" -d '{"is_active": false}'
# Immediate model test → still resolves to old connection (stale cache)
```

### 3.6 Verify Fix

```bash
# After fix: disable connection
curl -X PATCH "/providers/{id}" -d '{"is_active": false}'
# Immediate model test → "No active connection found" (cache is fresh)
```

---

## 4. Solution

### Changes

File: `backend/app/routers/providers/connections.py`

```python
# Added import
from app.services.proxy import invalidate_connection_cache

# In update_provider(), after db.flush():
await db.flush()
await db.refresh(conn)

# ↓ Added
invalidate_connection_cache(conn.provider)

return _connection_to_out(conn)
```

### Why This Is Sufficient

- `invalidate_connection_cache()` removes cache entry for that provider
- Next request calls `get_connections_cached()` → cache miss → fresh DB query
- New `is_active` value is immediately reflected
- No need for `reset_connection_rotation()` because round-robin state is not related
  to enable/disable connection

---

## 5. Impact

### Before Fix

```
User toggle connection → DB update → cache stale (30 seconds)
→ model test / chat request uses old data → error "Login expired"
```

### After Fix

```
User toggle connection → DB update → cache invalidated
→ model test / chat request uses new data → OK
```

### Scope

This bug is **NOT Qoder-specific**. All providers using connection cache
(`get_connections_cached`) are affected. Qoder is most noticeable because:
1. Qoder tokens expire faster than other providers
2. Qoder returns specific "Login expired" error which is confusing
3. Qoder users often switch between connections (multi-account)

---

## 6. Testing

### Manual Test

1. Open `/providers/qoder`
2. Test model `qmodel_latest` → should be OK
3. Disable connection, enable another connection
4. Test model `qmodel_latest` → should be OK (or "No active connection" if new one hasn't fetched models yet)
5. Switch back → test again → should be OK

### Automated Check

```bash
# Verify backend has no errors after fix
docker compose -f docker-compose.dev.yml logs backend --tail=5 2>&1 | grep -i error
# Expected: no errors

# Verify import is correct
docker compose -f docker-compose.dev.yml exec backend uv run python3 -c "
from app.routers.providers.connections import update_provider
print('Import OK')
"
```
