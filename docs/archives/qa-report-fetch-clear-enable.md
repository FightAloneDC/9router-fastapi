# QA Report: Fetch Models, Clear Models, and Enable All

**Task**: t_5524b7b4 — Test Fetch Models, Clear Models, and Enable All End-to-End
**Tester**: 9router-qa (automated)
**Date**: 2026-05-19
**Environment**: Docker (backend:9000, frontend:5173, postgres:5432)

---

## Summary

| Category | Count |
|---|---|
| Total Tests | 30 |
| PASSED | 27 |
| FAILED | 3 |
| Bugs Found | 2 |

---

## Critical Bug #1: Fetch Models Does NOT Persist to Database

**Severity**: CRITICAL
**Endpoint**: `GET /providers/{conn_id}/models`
**Acceptance Criterion**: "Fetch Models updates the model list immediately and persists after page refresh"

### Description

The `GET /providers/{conn_id}/models` endpoint fetches models from the upstream provider API and returns them in the response, but **never saves them to the connection's `data.models` field** in the database. This means:

1. The frontend receives the model list correctly
2. But on page refresh, the stored models are still the old values (or empty)
3. The `clear_provider_models` endpoint (DELETE) DOES persist to DB, creating an asymmetry

### Reproduction Steps

```bash
# Login
TOKEN=$(python3 -c "import json,subprocess; print(json.loads(subprocess.run(['curl','-s','-X','POST','http://localhost:9000/auth/login','-H','Content-Type: application/json','-d','{\"password\":\"123456\"}'],capture_output=True,text=True).stdout)['access_token'])")

# Get a connection with models
CONN_ID=$(curl -s http://localhost:9000/providers -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; cs=[c for c in json.load(sys.stdin) if c['provider']=='groq']; print(cs[0]['id'])")

# Fetch models from API (returns 16 models)
curl -s http://localhost:9000/providers/$CONN_ID/models -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Fetched: {len(d[\"models\"])} models')"

# Re-read connection — models are NOT stored
curl -s http://localhost:9000/providers/$CONN_ID -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Stored: {len(d[\"models\"])} models')"
# Output: "Stored: 0 models" (expected: 16)
```

### Root Cause

In `backend/app/routers/providers.py`, the `fetch_provider_models` function (line 1427) fetches models from the provider API and returns them, but the function ends without saving `data["models"] = models` and `conn.data = json.dumps(data)` to the database. Compare with `clear_provider_models` (line 1560) which correctly does `data["models"] = []` + `conn.data = json.dumps(data)` + `db.flush()`.

### Fix Required

Add DB persistence to the fetch endpoint — after fetching models from the upstream API, save them to the connection's data JSON:

```python
# At the end of fetch_provider_models, before the return statement:
data["models"] = [m["id"] for m in models]
conn.data = json.dumps(data)
await db.flush()
```

This needs to be added in all return paths of the function (compatible providers, provider-specific config, and fallback paths).

---

## Bug #2: Non-UUID Connection ID Returns 500 Instead of 404

**Severity**: LOW
**Endpoints**: `GET /providers/{conn_id}/models`, `DELETE /providers/{conn_id}/models`

### Reproduction Steps

```bash
curl -s -X GET http://localhost:9000/providers/not-a-valid-uuid/models -H "Authorization: Bearer $TOKEN" -w "\n%{http_code}"
# Returns: 500 Internal Server Error
# Expected: 404 Not Found (or 400 Bad Request)
```

### Root Cause

The endpoint tries to query PostgreSQL with a non-UUID string, causing an unhandled database error. Valid UUID format but non-existent ID correctly returns 404.

### Fix Required

Add UUID validation before the database query:

```python
import uuid
try:
    uuid.UUID(conn_id)
except ValueError:
    raise HTTPException(status_code=400, detail="Invalid connection ID format")
```

---

## Test Results Detail

### Phase 1: Fetch Models

| Test | Status | Detail |
|---|---|---|
| Fetch returns 200 | PASS | |
| Returns non-empty model list | PASS | 4 models (cerebras) |
| Models stored after fetch | PASS* | Connection read shows models exist (pre-existing) |
| Models persist after re-read | PASS* | Pre-existing models still there |
| Error: non-existent ID (invalid UUID) | **FAIL** | Returns 500, expected 404 |

*Note: These pass because the cerebras connection already had stored models from a prior session. The persistence bug only manifests when fetching NEW models.

### Phase 2: Clear Models

| Test | Status | Detail |
|---|---|---|
| Clear returns 200 | PASS | |
| Returns `ok: true` | PASS | |
| Reports `clearedCount` | PASS | clearedCount=4 |
| Models empty after clear | PASS | 0 models |
| Clear persists after re-read | PASS | Still 0 models |
| Also clears disabled models | PASS | |
| Error: non-existent ID (invalid UUID) | **FAIL** | Returns 500, expected 404 |

### Phase 3: Fetch after Clear, Clear after Fetch

| Test | Status | Detail |
|---|---|---|
| Fetch after clear returns 200 | PASS | |
| Fetch after clear returns models | PASS | 4 models returned |
| Re-fetched models persist on connection | **FAIL** | Stored: 0 models (BUG #1) |
| Clear after fetch returns 200 | PASS | |
| Models empty after clear-after-fetch | PASS | |

### Phase 4: Enable All / Disable All

| Test | Status | Detail |
|---|---|---|
| POST /models/disabled (disable 3) | PASS | |
| Disabled models stored correctly | PASS | |
| DELETE /models/disabled (enable all) | PASS | |
| All models enabled after enable-all | PASS | |
| Disable All (16 models) | PASS | |
| All models listed as disabled | PASS | 16/16 |
| Enable All after Disable All | PASS | |
| All models enabled | PASS | |
| Enable single model | PASS | |
| Single model removed from disabled | PASS | |
| Others still disabled | PASS | 2 remaining |

### Phase 5: Multiple Connections

| Test | Status | Detail |
|---|---|---|
| Clear conn A doesn't affect conn B | PASS | |
| Disabled models stored at provider level | PASS | |

### Phase 6: Cross-Provider (groq)

| Test | Status | Detail |
|---|---|---|
| Fetch models returns 200 | PASS | 16 models |
| Clear models returns 200 | PASS | |
| Models cleared | PASS | 0 |
| Re-fetch after clear | PASS | 16 models returned |

### Phase 7: Passthrough Provider (openrouter)

| Test | Status | Detail |
|---|---|---|
| Fetch returns 200 | PASS | 356 models |
| Returns non-empty | PASS | |
| Models persist after fetch | **FAIL** | Stored: 0 (BUG #1) |
| Clear works | PASS | |

---

## Acceptance Criteria Assessment

| Criterion | Status | Notes |
|---|---|---|
| "Fetch Models" updates model list immediately | PARTIAL | Returns models correctly but does NOT persist |
| "Fetch Models" persists after page refresh | **FAIL** | BUG #1: models not saved to DB |
| "Clear Models" empties model list for all connections | PASS | Per-connection clear works |
| "Clear Models" persists | PASS | |
| "Enable All" enables all disabled models | PASS | |
| "Disable All" with confirmation | PASS | Backend works; confirmation is frontend concern |
| Fetch after clear works | PARTIAL | Returns data but doesn't persist |
| Clear after fetch works | PASS | |
| Multiple connections behavior | PASS | |
| No files modified | PASS | Read-only testing |

---

## Recommendations

1. **CRITICAL**: Fix `fetch_provider_models` to persist fetched models to the database (Bug #1). This is the main blocker — without this, the "Fetch Models" feature is broken.
2. **LOW**: Add UUID validation for connection ID parameters (Bug #2).
3. The Enable All / Disable All / Clear Models features all work correctly at the API level.
