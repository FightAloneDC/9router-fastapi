# Plan: Fix FastAPI Swagger Auth

**Status:** Done  
**Root cause:** Swagger UI auth completely broken — cannot test any endpoint via Swagger  
**Estimated effort:** Low-Medium

---

## Problem Statement

Swagger UI at `http://localhost:9000/docs` is unusable for API testing because
the "Authorize" button fails. This blocks manual testing of all endpoints.

---

## Root Cause Analysis

### Problem 1: OAuth2 Form-Encoded vs JSON Body

The `OAuth2PasswordBearer(tokenUrl="/auth/login")` in `auth.py` tells Swagger
to use OAuth2 "password" flow. When user clicks "Authorize", Swagger sends:

```
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=123456&grant_type=password
```

But `/auth/login` expects JSON body:

```json
{"password": "123456"}
```

Result: **422 Unprocessable Entity** — user can never authorize in Swagger.

### Problem 2: Two Separate Auth Systems

The codebase has two independent auth mechanisms:

| System | Used By | Token Source | Validation |
|--------|---------|-------------|------------|
| JWT (`get_current_user`) | Dashboard routes (61 endpoints) | `/auth/login` returns JWT | Decode JWT, look up user |
| API Key (`validate_api_key`) | v1 proxy routes (5 endpoints) | `api_keys` table | Look up key in DB table |

These are completely independent. A JWT token from `/auth/login` does NOT
work for v1 proxy routes. An API key from the `api_keys` table does NOT
work for dashboard routes.

### Problem 3: api_keys Table is Empty

```
SELECT count(*) FROM api_keys;
→ 0 rows
```

And `requireApiKey=False` in settings, so `validate_api_key` returns `None`
(skips auth entirely). This means v1 proxy routes currently have NO auth.

### Verified Behavior

```bash
# Swagger sends this → FAILS (422)
curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=123456&grant_type=password"
→ {"detail": "Input should be a valid dictionary or object..."}

# This works → SUCCESS
curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}'
→ {"access_token": "eyJhbG...", "token_type": "bearer"}

# JWT works for dashboard routes
curl http://localhost:9000/providers/client -H "Authorization: Bearer $JWT"
→ {"connections": [...]}

# JWT works for v1 routes too (because requireApiKey=False, auth skipped)
curl http://localhost:9000/v1/models -H "Authorization: Bearer $JWT"
→ {"object": "list", "data": [...]}
```

---

## Current Auth Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           FastAPI Application            │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                     │
          ┌─────────▼──────────┐            ┌────────────▼───────────┐
          │  Dashboard Routes  │            │    v1 Proxy Routes     │
          │  (61 endpoints)    │            │    (5 endpoints)       │
          │                    │            │                        │
          │  /providers/*      │            │  /v1/chat/completions  │
          │  /settings         │            │  /v1/models            │
          │  /combos           │            │  /v1/embeddings        │
          │  /usage            │            │  /v1/audio/speech      │
          │  /api-keys         │            │  /v1/audio/transcr.    │
          │  ...               │            │  + future endpoints    │
          └────────┬───────────┘            └───────────┬────────────┘
                   │                                     │
          ┌────────▼───────────┐            ┌────────────▼───────────┐
          │  get_current_user  │            │   validate_api_key     │
          │  (JWT validation)  │            │   (DB api_keys lookup) │
          │                    │            │                        │
          │  Decodes JWT from  │            │  Checks Bearer token   │
          │  Authorization     │            │  against api_keys      │
          │  header using      │            │  table. Returns None   │
          │  SECRET_KEY        │            │  if requireApiKey=False│
          └────────────────────┘            └────────────────────────┘
```

---

## Solution Options

### Option A: HTTPBearer + Form-Compatible Login (Recommended)

**Approach:** Replace `OAuth2PasswordBearer` with `HTTPBearer` for Swagger,
and add form-encoded support to `/auth/login`.

**Pros:**
- Simplest fix — `HTTPBearer` shows a text field where user pastes JWT
- No OAuth2 complexity
- Works for both dashboard and v1 routes (both accept Bearer token)
- Login endpoint supports both JSON and form-encoded

**Cons:**
- User must manually copy JWT from `/auth/login` response and paste into Swagger
- Not as seamless as OAuth2 "Authorize" flow

**Changes:**
1. `backend/app/routers/auth.py` — Replace `OAuth2PasswordBearer` with `HTTPBearer`
2. `backend/app/routers/auth.py` — Add form-encoded support to `/auth/login`

### Option B: Dual Security Schemes

**Approach:** Register both JWT and API Key as separate security schemes in
Swagger. Dashboard routes use JWT, v1 routes use API Key.

**Pros:**
- Matches the actual auth architecture
- Clear separation between dashboard and v1 auth

**Cons:**
- More complex — need to annotate each route with correct security scheme
- Two separate "Authorize" buttons in Swagger
- API key scheme still requires creating keys first

### Option C: Unify Auth (JWT for Everything)

**Approach:** Make v1 proxy routes also accept JWT tokens (in addition to API
keys). Single auth system for everything.

**Pros:**
- One token works everywhere
- Swagger auth is simple
- Matches user expectation (login once, test everything)

**Cons:**
- Changes v1 proxy auth behavior
- Need to decide priority when both JWT and API key are present

---

## Recommended Solution: Option A

### Phase 1 — Fix Login Endpoint for Form-Encoded

**File:** `backend/app/routers/auth.py`

Add a form-compatible login endpoint that Swagger's OAuth2 flow can call:

```python
from fastapi import Form
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/token", response_model=Token, include_in_schema=False)
async def login_for_swagger(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2-compatible login endpoint for Swagger UI.
    
    Accepts form-encoded data (username + password) as required by
    OAuth2 password flow. Maps to the existing password-only auth.
    The username field is ignored — only password is checked.
    """
    any_user = await get_any_user(db)
    
    if any_user is None:
        if form_data.password != DEFAULT_PASSWORD:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )
        admin = await ensure_admin_user(db)
        token = create_access_token(data={"sub": admin.username})
        return Token(access_token=token)
    
    user = await authenticate_user(db, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
        )
    token = create_access_token(data={"sub": user.username})
    return Token(access_token=token)
```

Then update `OAuth2PasswordBearer` to point to `/auth/token`:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
```

**Why `/auth/token` and not modify `/auth/login`:**
- `/auth/login` stays clean (JSON only, used by frontend)
- `/auth/token` is the OAuth2 standard endpoint name
- `include_in_schema=False` hides it from Swagger docs (it's only for OAuth2 flow)

### Phase 2 — Make v1 Routes Accept JWT Too

**File:** `backend/app/services/api_key_auth.py`

Modify `validate_api_key` to also accept JWT tokens as fallback:

```python
async def validate_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Validate Bearer token for /v1/ routes.
    
    Accepts both API keys (from api_keys table) and JWT tokens.
    Priority: API key first, then JWT fallback.
    Returns None if auth not required (requireApiKey=False).
    """
    require_key = await _require_api_key_setting(db)
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        if not require_key:
            return None  # No auth required, no token provided
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    
    token = auth_header[7:]
    
    # Try API key first
    result = await db.execute(
        select(ApiKey).where(ApiKey.key == token, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if api_key:
        return {"id": api_key.id, "name": api_key.name, "auth_type": "api_key"}
    
    # Fallback: try JWT
    from app.services.auth import decode_access_token, get_user_by_username
    payload = decode_access_token(token)
    if payload and payload.get("sub"):
        user = await get_user_by_username(db, payload["sub"])
        if user:
            return {"id": user.id, "name": user.username, "auth_type": "jwt"}
    
    if not require_key:
        return None  # Auth not required, token was invalid but we don't care
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or inactive API key / JWT token",
    )
```

**Key changes:**
- Try API key first (existing behavior)
- If not an API key, try decoding as JWT
- If JWT is valid, return user info
- If `requireApiKey=False` and token is invalid, still return None (don't block)

### Phase 3 — Verify Swagger Works

After Phase 1 + Phase 2:

1. Open `http://localhost:9000/docs`
2. Click "Authorize" button
3. Swagger shows OAuth2 form with username + password fields
4. Enter: username=`admin`, password=`123456`
5. Click "Authorize" → should succeed
6. Test any dashboard endpoint → should work (JWT auth)
7. Test any v1 endpoint → should work (JWT accepted as fallback)

### Phase 4 — Testing

**Test 1 — Swagger OAuth2 login:**
```bash
# Simulate what Swagger does
curl -s -X POST http://localhost:9000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=123456&grant_type=password" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('token_type:', d.get('token_type'))
print('token:', d.get('access_token', '')[:30] + '...')
"
```
Expected: `token_type: bearer`, token starts with `eyJhbG`.

**Test 2 — Dashboard route with JWT from /auth/token:**
```bash
JWT=$(curl -s -X POST http://localhost:9000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=123456" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:9000/providers/client \
  -H "Authorization: Bearer $JWT" | python3 -c "import sys,json;d=json.load(sys.stdin);print('connections:', len(d.get('connections',[])))"
```
Expected: connections count > 0.

**Test 3 — v1 route with JWT from /auth/token:**
```bash
curl -s http://localhost:9000/v1/models \
  -H "Authorization: Bearer $JWT" | python3 -c "import sys,json;d=json.load(sys.stdin);print('models:', len(d.get('data',[])))"
```
Expected: models count > 0.

**Test 4 — Original /auth/login still works (JSON):**
```bash
curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('token:', d.get('access_token','')[:30]+'...')"
```
Expected: Token returned.

**Test 5 — Invalid password rejected:**
```bash
curl -s -X POST http://localhost:9000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=wrong" | python3 -c "import sys,json;print(json.load(sys.stdin))"
```
Expected: `401` with `"Incorrect password"`.

**Test 6 — Swagger UI manual test:**
1. Open http://localhost:9000/docs
2. Click "Authorize"
3. Enter username=`admin`, password=`123456`
4. Click "Authorize" → green checkmark
5. Try `GET /providers` → 200 with data
6. Try `GET /v1/models` → 200 with model list

---

## Phase 5 — Report

1. Update `docs/porting-status.md` — add note about Swagger auth fix.
2. Update this file — mark status as `Done`.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/routers/auth.py` | Add `/auth/token` endpoint (form-encoded), update `tokenUrl` to `/auth/token` |
| `backend/app/services/api_key_auth.py` | Add JWT fallback in `validate_api_key` |

No DB migrations. No frontend changes. No new dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| /auth/token endpoint | Low | Copy login logic, accept form data |
| OAuth2PasswordBearer tokenUrl | Trivial | One-line change |
| JWT fallback in validate_api_key | Low | Add decode_access_token check |
| Testing | Low | curl + manual Swagger test |

**Overall:** Low complexity. Two small changes, both straightforward.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|------|
| Username field ignored | OAuth2 form has username field but 9Router uses password-only auth. Username is accepted but ignored. |
| requireApiKey behavior | When `requireApiKey=True`, invalid tokens return 401. When `False`, invalid tokens are silently ignored (auth skipped). |
| API key vs JWT priority | API keys are checked first. If both an API key and JWT exist with the same token value (unlikely), API key wins. |
| Swagger "try it out" | After authorizing, all Swagger "Try it out" calls will include the JWT. Works for both dashboard and v1 routes. |
| /auth/token hidden from docs | `include_in_schema=False` so it doesn't clutter the Swagger docs. Only the OAuth2 flow uses it. |
