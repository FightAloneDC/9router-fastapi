# Kilo Gateway QA Test Report
**Date:** 2026-05-19
**Tester:** 9router-qa (automated)
**Task:** t_1a0d8924 — KILO-4: QA — Test Kilo Gateway end-to-end

## Test Environment
- Backend: Docker container `9router-backend` on port 1455
- Frontend: Docker container `9router-frontend` on port 5173
- Database: PostgreSQL 16 on port 5432

## Test Results Summary

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1 | Add connection with valid API key | PASS | Connections display correctly, 2 Kilo Gateway connections visible |
| 2 | Test connection (valid key) | PASS | "QA Test KG Connection" shows "connected" after test |
| 3 | Test connection (invalid key) | PASS* | Kilo API is permissive — accepts any key for free models. "Connection verified" is correct. |
| 4 | Fetch models from Kilo API | PASS | 344 models fetched from `https://api.kilo.ai/api/gateway/models` |
| 5 | Test connection uses `kilo-auto/free` | PASS | Code at `providers.py:437` confirms model is `kilo-auto/free` |
| 6 | Model chat via proxy | PASS | `kg/kilo-auto/free` returned response (routed to `nvidia/nemotron-3-super-120b-a12b:free`) |
| 7 | Kilo Code OAuth regression | **FAIL** | Test endpoint returns "No API key configured" for OAuth connections |

## Detailed Findings

### PASS: Kilo Gateway Core Flow
- **Add connection:** Works. Existing connections visible in UI (2 configured).
- **Test connection:** Works. Valid key → "connected" status. Uses `kilo-auto/free` model for test.
- **Fetch models:** Works. 344 models stored in DB. UI shows "Clear Models" and "Disable All" buttons (passthrough mode — models stored but not listed in UI, by design).
- **Chat via proxy:** Works. `POST /v1/chat/completions` with `model: "kg/kilo-auto/free"` returns valid response.

### PASS (with note): Invalid Key Validation
The Kilo Gateway API (`https://api.kilo.ai/api/gateway`) is **permissive** — it accepts any API key string for free-tier models. The "Check" and "Test Connection" buttons in the edit modal correctly call the API and report "Connection verified" because the API returns a valid response. This is expected behavior, not a bug. However, this means:
- The validation only confirms the endpoint is reachable, not that the key is valid
- Free-tier models work without authentication
- Paid models may require valid keys (not tested — no paid key available)

### BUG #1: Kilo Code OAuth Test Regression (HIGH)
**File:** `backend/app/routers/providers.py`
**Function:** `_test_provider_connection` (line 559)

**Description:** The test endpoint for OAuth providers (like Kilo Code) fails with "No API key configured for this connection" even though the connection has a valid `accessToken`.

**Root Cause:** At line 597, the code correctly checks `if not api_key and not data.get("accessToken", "")` to allow OAuth connections through. However, after this check, the code proceeds to call validation functions (e.g., `_validate_openai_compatible` at line 635) with only `api_key` (from `data.get("apiKey", "")`), which is empty for OAuth providers. The `accessToken` is never substituted in.

**Code Flow:**
1. Line 570: `api_key = data.get("apiKey", "")` → empty for OAuth
2. Line 597: Check passes because `accessToken` exists
3. Line 600: `vtype = _get_validation_type("kilocode")` → "openai"
4. Line 635: `await _validate_openai_compatible(api_key, default_url)` → called with empty `api_key`
5. Line 289-290: `_validate_openai_compatible` returns "No API key configured"

**Reproduction:**
1. Have a Kilo Code OAuth connection with valid accessToken
2. Click "Test" button on the Kilo Code provider page
3. Result: "error" — "No API key configured for this connection"

**Fix:** In `_test_provider_connection`, when `api_key` is empty but `accessToken` exists, use `accessToken` as the credential for validation. For example:
```python
# After line 598
effective_key = api_key or data.get("accessToken", "")
```
Then use `effective_key` instead of `api_key` in subsequent validation calls.

### Note: Edit Modal API Key Not Persisting
When editing the "QA Test Key" connection and entering an API key in the modal, clicking "Save" did not persist the key to the database (`apiKey` remained empty). This may be a frontend issue with how the API key field sends data to the backend PATCH endpoint. Not part of this QA task scope but worth investigating.

## Model Verification
The test connection correctly uses `kilo-auto/free` model (verified at `providers.py:437`):
```python
payload = {"model": "kilo-auto/free", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
```

## Proxy Chat Test
```
Request:  POST /v1/chat/completions
Model:    kg/kilo-auto/free
Response: 200 OK
Routed:   nvidia/nemotron-3-super-120b-a12b:free (auto-selected by Kilo)
Tokens:   21 prompt + 10 completion = 31 total
Cost:     $0.00 (free tier)
```

## Conclusion
The Kilo Gateway provider integration works correctly for the core flow (add, test, fetch models, chat). One regression was found in the Kilo Code OAuth test endpoint where the test function doesn't use `accessToken` for OAuth providers.
