# Qoder Bug Fixing — Full Discussion Log

Date: 2026-06-06 to 2026-06-09 (3 days)

---

## Table of Contents

1. [Bug #1: Connection Switch → Stale Cache (Login Expired)](#bug-1-connection-switch--stale-cache-login-expired)
2. [Bug #2: Token Expires ~24 Hours (Not 30 Days)](#bug-2-token-expires-24-hours-not-30-days)
3. [Bug #3: Refresh Token Endpoint Wrong (403)](#bug-3-refresh-token-endpoint-wrong-403)
4. [Bug #4: Auto-Refresh Not Working for Idle Connections](#bug-4-auto-refresh-not-working-for-idle-connections)
5. [Deep Investigation: Qoder Token Types](#deep-investigation-qoder-token-types)
6. [Changes Summary](#changes-summary)
7. [Related Documents](#related-documents)

---

## Bug #1: Connection Switch → Stale Cache (Login Expired)

### Symptoms

User toggles enable/disable Qoder connection in UI, then subsequent requests fail with "Login expired" error even though the enabled connection has a valid token.

### Root Cause

`update_provider()` in `backend/app/routers/providers/connections.py` **did not call `invalidate_connection_cache()`** after DB update. Proxy service has a 30-second cache for connection data, so DB changes were not immediately reflected.

### Investigation

```
User toggle connection → update_provider() → DB updated
                                        ↓
                              Cache still uses old data (30s TTL)
                                        ↓
                              Proxy resolve → uses old connection (expired)
                                        ↓
                              "Login expired"
```

### Fix

Added `invalidate_connection_cache(conn.provider)` in `update_provider()` after `db.flush()` + `db.refresh(conn)`:

```python
# backend/app/routers/providers/connections.py (line ~341)
await db.flush()
await db.refresh(conn)
invalidate_connection_cache(conn.provider)  # ← ADDED
```

### Files

- `backend/app/routers/providers/connections.py` — added import + invalidate cache

---

## Bug #2: Token Expires ~24 Hours (Not 30 Days)

### Symptoms

Qoder tokens imported via PAT (`pt-xxx`) expire in ~24 hours, even though qodercli documentation says tokens last ~30 days.

### Root Cause

**Different token types:**

| Token Type | Prefix | Lifetime | Source |
|------------|--------|----------|--------|
| Device Token | `dt-` | ~30 days | Device flow (qodercli login) |
| Job Token | `jt-` | ~24 hours | PAT exchange (`/api/v1/jobToken/exchange`) |
| Refresh Token | `jrt-` | ~48 hours | Comes with job token |

9router uses PAT import → gets **Job Token** (`jt-`) which expires in ~24 hours, not Device Token (`dt-`) which lasts ~30 days.

### Investigation

```bash
# qodercli stores device token (dt-) in ~/.qoder/.auth/user (encrypted)
# 9router PAT exchange → /api/v1/jobToken/exchange → job token (jt-)
```

Response from PAT exchange:
```json
{
  "token": "jt-xxx",
  "expires_in": 86400000,    // 24 hours (in ms)
  "refreshToken": "jrt-xxx",
  "refresh_token_expires_in": 172800000  // 48 hours
}
```

### Decision

Not implementing device flow because:
- Device flow requires browser interaction (user must open URL)
- PAT exchange is easier (copy-paste token)
- With auto-refresh, tokens never expire while server is running

---

## Bug #3: Refresh Token Endpoint Wrong (403)

### Symptoms

All refresh token attempts fail with HTTP 403.

### Root Cause

The refresh endpoint used was **WRONG**:

| | Wrong (old 9router) | Correct (qodercli) |
|---|---|---|
| URL | `center.qoder.sh/algo/api/v3/user/refresh_token` | `openapi.qoder.sh/api/v1/jobToken/refresh` |
| Response | 403 Forbidden | 200 OK |

### Investigation

Reverse-engineering from `qodercli.js` (33MB bundle):

```javascript
// qodercli source (minified)
async refreshAccessTokenAsync() {
    const response = await this.httpClient.post(
        `${this.baseUrl}/api/v1/jobToken/refresh`,  // ← openapi.qoder.sh
        { refresh_token: this.cachedUserInfo.refresh_token }
    );
    // ...
}
```

### Fix

```python
# backend/app/providers/qoder/constants.py
# BEFORE:
QODER_REFRESH_TOKEN_URL = f"{QODER_CENTER_BASE}/algo/api/v3/user/refresh_token"
# AFTER:
QODER_REFRESH_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/refresh"
```

### Response Format

```json
{
  "token": "jt-xxx",
  "created_at": "2026-06-09T17:13:54Z",
  "expires_at": "2026-06-10T17:13:54Z",
  "expires_in": 86400000,
  "refresh_token": "jrt-yyy",
  "refresh_token_expires_at": "2026-06-11T17:13:54Z",
  "refresh_token_expires_in": 172800000
}
```

---

## Bug #4: Auto-Refresh Not Working for Idle Connections

### Symptoms

Qoder connections that are idle for >24 hours expire and cannot be used without re-importing PAT.

### Root Cause

No auto-refresh mechanism. Tokens were only refreshed when a request failed (on-demand). If no requests were made, tokens expired silently.

### Fix: Dual Refresh Strategy

#### 1. On-Demand Refresh (when request fails)

Proxy detects 401/403 from Qoder → tries refresh → retries request (transparent to client).

```python
# backend/app/routers/v1_proxy/chat.py
except httpx.HTTPStatusError as e:
    if e.response.status_code in (401, 403):
        from app.routers.v1_proxy.shared import _try_qoder_token_refresh
        if await _try_qoder_token_refresh(target, db):
            continue  # retry with fresh token
```

Also when build request fails:
```python
except Exception as e:
    if target.provider == "qoder" and target.connection_id:
        from app.routers.v1_proxy.shared import _try_qoder_token_refresh
        if await _try_qoder_token_refresh(target, db):
            continue  # retry with fresh token
```

#### 2. Background Refresh (periodic every 5 minutes)

Existing background task in `token_refresh.py` was modified to also refresh Qoder tokens:

```python
# backend/app/services/token_refresh.py
async def check_and_refresh_tokens():
    # ... existing OAuth refresh logic ...
    
    # Add Qoder refresh
    from app.providers.qoder.auth import refresh_all_qoder_connections
    qoder_results = await refresh_all_qoder_connections()
```

```python
# backend/app/providers/qoder/auth.py
async def refresh_all_qoder_connections() -> dict[str, bool]:
    """Background task: refresh all Qoder connections every 5 min."""
    for conn in connections:
        new_tokens = await refresh_job_token(refresh_token)
        if new_tokens:
            data["accessToken"] = new_tokens["access_token"]
            data["refreshToken"] = new_tokens["refresh_token"]
            # ... update DB
```

### Token Lifecycle with Auto-Refresh

```
Hour 0:     Import PAT → get jt-xxx + jrt-xxx
Hour 0-24:  Token fresh, works directly
Hour 5:     Background refresh → new token, timer reset
Hour 10:    Background refresh → new token, timer reset
Hour 15:    Background refresh → new token, timer reset
...
(while server is running, tokens never expire)

Hour X:     Server down
Hour X+48:  Refresh token expires → need to re-import PAT
```

---

## Deep Investigation: Qoder Token Types

### Device Token (`dt-xxx`)

- Source: Device flow (browser-based OAuth)
- Lifetime: ~30 days
- Stored: `~/.qoder/.auth/user` (encrypted)
- Used by: qodercli, Veria IDE
- Refreshable: Yes, via device flow

### Job Token (`jt-xxx`)

- Source: PAT exchange (`/api/v1/jobToken/exchange`)
- Lifetime: ~24 hours
- Stored: Database (plaintext in JSON blob)
- Used by: 9router
- Refreshable: Yes, with refresh token

### Refresh Token (`jrt-xxx`)

- Source: Comes with job token
- Lifetime: ~48 hours
- Stored: Database (plaintext in JSON blob)
- Endpoint: `POST openapi.qoder.sh/api/v1/jobToken/refresh`
- Each refresh: get NEW access token + NEW refresh token

### Personal Access Token (`pt-xxx`)

- Source: qoder.com/account/integrations
- Lifetime: Does not expire (until revoked)
- Used for: Exchange to job token
- Cannot be used directly for API calls

### Complete Flow

```
User gets PAT (pt-xxx) from qoder.com
        ↓
9router: POST /api/v1/jobToken/exchange {personal_token: "pt-xxx"}
        ↓
Response: {token: "jt-xxx", refreshToken: "jrt-xxx"}
        ↓
Store in DB, use for COSY-signed requests
        ↓
Every 5 minutes: POST /api/v1/jobToken/refresh {refresh_token: "jrt-xxx"}
        ↓
Response: {token: "jt-yyy", refreshToken: "jrt-yyy"}  ← new token
        ↓
Update DB, reset timer
```

---

## Changes Summary

### Files Modified

| File | Changes |
|------|---------|
| `backend/app/providers/qoder/constants.py` | Fix refresh endpoint URL |
| `backend/app/providers/qoder/auth.py` | Added `refresh_job_token()`, `try_refresh_connection()`, `refresh_all_qoder_connections()` |
| `backend/app/providers/qoder/handler.py` | `validate_connection()` calls `fetch_user_info()` |
| `backend/app/providers/qoder/cosy.py` | Refactor COSY signing |
| `backend/app/routers/providers/connections.py` | Added `invalidate_connection_cache()` after update |
| `backend/app/routers/models.py` | Reduce timeout 60s → 20s |
| `backend/app/routers/v1_proxy/chat.py` | Added auto-refresh on 401/403 + build failure |
| `backend/app/routers/v1_proxy/messages.py` | Added auto-refresh on 401/403 |
| `backend/app/routers/v1_proxy/responses.py` | Added auto-refresh on 401/403 |
| `backend/app/routers/v1_proxy/shared.py` | Added `_try_qoder_token_refresh()` helper |
| `backend/app/services/token_refresh.py` | Added Qoder refresh to background task |

### Files Created

| File | Description |
|------|-------------|
| `backend/app/providers/DOCS/BUG-QODER-CACHE-STALE.md` | Cache stale bug documentation |
| `backend/tests/test_qoder_cosy.py` | Unit tests COSY signing |

### Git Commit

```
736bfd2 fix(qoder): auto-refresh token + correct refresh endpoint
```

---

## Related Documents

- [QODER_PROVIDER_DOC.md](./QODER_PROVIDER_DOC.md) — Full Qoder provider architecture
- [QODER_NEXT_SESSION_PROMPT.md](./QODER_NEXT_SESSION_PROMPT.md) — Context for next AI session
- [BUG-QODER-CACHE-STALE.md](./BUG-QODER-CACHE-STALE.md) — Cache stale bug details

---

## Testing

### Test Auto-Refresh (Simulate Token Expiration)

```bash
# 1. Set fake expired token
docker exec 9router-postgres psql -U dev_9route -d db_9route -c "
UPDATE provider_connections 
SET data = jsonb_set(data::jsonb, '{accessToken}', '\"jt-FAKEEXPIRED\"')
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';
"

# 2. Test request (will auto-refresh)
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"qd/qoder/qmodel_latest","messages":[{"role":"user","content":"hi"}]}'

# 3. Verify token updated
docker exec 9router-postgres psql -U dev_9route -d db_9route -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';
"
```

### Test Background Refresh

```bash
# 1. Record token
docker exec 9router-postgres psql -U dev_9route -d db_9route -t -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';"

# 2. Wait 6 minutes
sleep 360

# 3. Check token changed
docker exec 9router-postgres psql -U dev_9route -d db_9route -t -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';"
```

---

## Lessons Learned

1. **Never assume endpoints** — Qoder has 2 different base URLs (openapi vs center), the same endpoint can return 403 on one and 200 on the other.

2. **Reverse-engineer from source** — qodercli bundle (33MB) has all the answers, but requires careful grep because it's minified.

3. **Token types matter** — `dt-` vs `jt-` vs `jrt-` have different lifetimes and refresh mechanisms.

4. **Cache invalidation** — Always invalidate cache after DB update, especially for proxy/router with connection pools.

5. **Background task** — For token expiration, don't rely only on on-demand refresh. Background tasks ensure tokens stay alive even when idle.
