# Fix: Qoder "Test Model" Button Failure

## Root Cause

**`_map_qoder_tokens()` in `oauth_providers.py` does not extract `userId` from `user_info`.**

When a Qoder connection is created via OAuth device flow:

1. `poll_device_token()` returns `{ access_token, user_id, ... }` — `user_id` may be absent in device token response
2. `_post_exchange_qoder()` fetches `user_info = fetch_user_info(access_token)` → returns `{ id, email, name, ... }`
3. `_map_qoder_tokens(tokens, extra)` only checks `tokens.get("user_id")` — **never reads `extra["userInfo"]["id"]`**
4. `providerSpecificData` = `{}` → saved as `None` in DB
5. Test model → `build_cosy_headers()` → `ValueError("cosy: user id is empty")` → test gagal

**Contrast with PAT flow** (`auth.py:341`): `import_pat()` correctly does `user_info.get("id") or user_info.get("uid") or user_info.get("userId")`. Device flow doesn't reuse this pattern.

## Architecture Violation

Current `_map_qoder_tokens()` and `_post_exchange_qoder()` live in `oauth_providers.py` — these are Qoder-specific logic that MUST live in `backend/app/providers/qoder/`.

## Implementation Plan

### Step 1: Add `map_device_tokens()` to `providers/qoder/auth.py`

**File**: `backend/app/providers/qoder/auth.py`

Add new function after `import_pat()` (after line 352):

```python
async def map_device_tokens(tokens: dict, user_info: dict | None = None) -> dict:
    """Map device flow tokens to connection data format.

    Extracts userId from user_info (same logic as import_pat).
    Called by oauth_providers._map_qoder_tokens().

    Args:
        tokens: Raw token data from poll_device_token()
        user_info: User info from fetch_user_info() (via _post_exchange_qoder)

    Returns:
        Dict with accessToken, refreshToken, providerSpecificData, etc.
    """
    user_info = user_info or {}

    # Extract userId — same logic as import_pat() line 341
    user_id = (
        tokens.get("user_id")
        or user_info.get("id")
        or user_info.get("uid")
        or user_info.get("userId")
    )

    psd = {}
    if user_id:
        psd["userId"] = user_id
    if tokens.get("_qoderMachineId"):
        psd["machineId"] = tokens["_qoderMachineId"]

    email = tokens.get("email") or user_info.get("email")
    display_name = (
        tokens.get("display_name")
        or user_info.get("name")
        or user_info.get("displayName")
    )

    return {
        "accessToken": tokens.get("access_token"),
        "refreshToken": tokens.get("refresh_token"),
        "expiresIn": tokens.get("expires_in"),
        "email": email,
        "displayName": display_name,
        "providerSpecificData": psd if psd else None,
    }
```

### Step 2: Update `__init__.py` to export new function

**File**: `backend/app/providers/qoder/__init__.py`

Add `map_device_tokens` to imports and `__all__`.

### Step 3: Delegate `_map_qoder_tokens()` in `oauth_providers.py`

**File**: `backend/app/services/oauth_providers.py:1229-1252`

Replace inline logic with delegation to `providers/qoder/auth.py`:

```python
def _map_qoder_tokens(tokens: dict, extra: Optional[dict] = None) -> dict:
    """Map Qoder tokens to standard format."""
    from app.providers.qoder.auth import map_device_tokens

    user_info = (extra or {}).get("userInfo", {})
    return map_device_tokens(tokens, user_info)
```

### Step 4 (Optional): Delegate `_post_exchange_qoder()` similarly

Move the `_post_exchange_qoder` logic to `providers/qoder/auth.py` as `post_exchange_device_flow()` and have `oauth_providers.py` delegate to it. This keeps all Qoder-specific logic in the provider package.

### Step 5: Verify

1. Delete existing Qoder connection to force re-creation
2. Re-authenticate via device flow
3. Check DB: `providerSpecificData` should contain `userId`
4. Click "Test Model" → should return `{"ok": true}`

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')

curl -s -X POST http://localhost:9000/models/test \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "qd/qoder/auto"}' | jq .
```

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/providers/qoder/auth.py` | Add `map_device_tokens()` function |
| `backend/app/providers/qoder/__init__.py` | Export `map_device_tokens` |
| `backend/app/services/oauth_providers.py:1229-1252` | Delegate `_map_qoder_tokens` to `providers/qoder/auth.map_device_tokens` |

## Other Issues Found (Low Priority)

- **Silent error swallowing**: `proxy.py:684-687` catches ValueError and returns `[]`, hiding real errors
- **Broken endpoint**: `testing.py:228` imports non-existent functions (dead code, not called by frontend)
- **`max_tokens: 1`**: Test body uses very low value, Qoder might reject
- **15s timeout**: Test endpoint buffers full SSE with 15s timeout, chat uses 300s
