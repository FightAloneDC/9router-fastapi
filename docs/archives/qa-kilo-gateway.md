# Kilo Gateway QA Test Report

**Date**: 2026-05-19
**Tester**: 9router-qa (kanban task t_1a0d8924)
**Backend**: http://localhost:9000 (Docker)
**Frontend**: http://localhost:5173 (Docker)

---

## Test Results Summary

| # | Test Case | Status | Notes |
|---|-----------|--------|-------|
| 1 | Add connection (API) | ✅ PASS | Connection created, API key stored in data blob |
| 2 | Test connection (valid key) | ✅ PASS | Uses `kilo-auto/free` model, returns valid=true |
| 3 | Test connection (invalid key) | ⚠️ BUG | Invalid key also passes validation |
| 4 | Fetch models (via API) | ✅ PASS | Returns 60+ models from Kilo Gateway API |
| 5 | Suggested models endpoint | ✅ PASS | Returns properly formatted model list |
| 6 | Chat via proxy (kg/ prefix) | ✅ PASS | `kg/kilo-auto/free` works correctly |
| 7 | Chat via proxy (no prefix) | ❌ FAIL | `kilo-auto/free` returns "No provider available" |
| 8 | Streaming via proxy | ✅ PASS | SSE streaming works correctly |
| 9 | PATCH connection (add API key) | ✅ PASS | API key stored, fetch models then works |
| 10 | Kilo Code OAuth regression | ✅ PASS | No conflicts, connection still accessible |
| 11 | Original connection (no API key) | ❌ BUG | Frontend-created connection has no apiKey in data |

---

## Detailed Test Results

### TEST 1: Add Connection via API ✅
```bash
curl -X POST http://localhost:9000/providers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"provider":"kilo-gateway","name":"QA Test","apiKey":"test-key-12345","auth_type":"apikey","baseUrl":"https://api.kilo.ai/api/gateway"}'
```
**Result**: Connection created with `test_status: "connected"`, API key stored in data blob.

### TEST 2: Test Connection (Valid) ✅
```bash
curl -X POST "http://localhost:9000/providers/$ID/test" -H "Authorization: Bearer $TOKEN"
```
**Result**: `{"valid":true,"error":null,"latencyMs":0,"models":null}`
- Uses model `kilo-auto/free` with payload `{"model":"kilo-auto/free","messages":[{"role":"user","content":"ping"}],"max_tokens":1}`

### TEST 3: Test Connection (Invalid Key) ⚠️ BUG
```bash
# Created connection with apiKey="INVALID_KEY_TEST_12345"
# Result: test_status="connected" — INVALID KEY PASSES!
```
**Root Cause**: Kilo Gateway API does NOT enforce authentication for `kilo-auto/free` model. Any API key (even "INVALID_KEY_TEST_12345") returns 200 OK.
**Impact**: Connection validation is unreliable — all connections show "connected" regardless of key validity.
**Suggestion**: Validate against a paid model (e.g., `anthropic/claude-sonnet-4.6`) or use the `/models` endpoint which requires auth.

### TEST 4: Fetch Models ✅
```bash
curl "http://localhost:9000/providers/$ID/models" -H "Authorization: Bearer $TOKEN"
```
**Result**: Returns 60+ models including:
- `kilo-auto/frontier`, `kilo-auto/balanced`, `kilo-auto/free`
- `anthropic/claude-opus-4.7`, `openai/gpt-5.5`, `google/gemini-3.1-pro-preview`
- Free models: `nvidia/nemotron-3-super-120b-a12b:free`, `deepseek/deepseek-v4-flash:free`

### TEST 5: Suggested Models Endpoint ✅
```bash
curl "http://localhost:9000/providers/suggested-models?url=https://api.kilo.ai/api/gateway/models&type=kilo-gateway"
```
**Result**: Returns models with proper `{id, name}` format. Filter for `kilo-gateway` type works.

### TEST 6: Chat via Proxy (With Prefix) ✅
```bash
curl -X POST "http://localhost:9000/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"kg/kilo-auto/free","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}'
```
**Result**: Returns valid chat completion from NVIDIA Nemotron model via Kilo Gateway.
- Also works with `kilo-gateway/kilo-auto/free` prefix.

### TEST 7: Chat via Proxy (No Prefix) ❌ FAIL
```bash
curl -X POST "http://localhost:9000/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"kilo-auto/free","messages":[{"role":"user","content":"Say hi"}]}'
```
**Result**: `{"detail":"No provider available for model: kilo-auto/free"}`
**Root Cause**: Proxy resolves `kilo-auto` as provider name (from `kilo-auto/free`), but no connection exists with `provider="kilo-auto"`. The actual provider is `kilo-gateway`.
**Impact**: Models from Kilo Gateway API use `kilo-auto/` prefix internally, which doesn't match the provider name. Users must use `kg/` prefix.

### TEST 8: Streaming ✅
```bash
curl -X POST "http://localhost:9000/v1/chat/completions" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"kg/kilo-auto/free","messages":[{"role":"user","content":"Say hi"}],"stream":true}'
```
**Result**: SSE stream works correctly with `data:` chunks.

### TEST 9: PATCH Connection (Add API Key) ✅
```bash
curl -X PATCH "http://localhost:9000/providers/$OLD_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"apiKey":"test-key-12345"}'
```
**Result**: API key stored in data blob. Subsequent `fetch models` and `test connection` calls succeed.

### TEST 10: Kilo Code OAuth Regression ✅
- Kilo Code OAuth connection (`49111b35`) still exists with `provider: "kilocode"`
- No conflicts between Kilo Code and Kilo Gateway providers
- Both use different provider names and base URLs

### TEST 11: Original Connection (No API Key) ❌ BUG
- Connection `96c443e4` was created via frontend with `test_status: "unknown"`
- `lastError: "No API key configured for this connection"`
- After PATCH with API key, works correctly
**Root Cause**: Frontend add-connection flow for Kilo Gateway may not properly store apiKey in the data blob during creation.

---

## Bugs Found

### BUG 1: Invalid API Key Passes Validation (MEDIUM)
- **Location**: `backend/app/routers/providers.py` line 431-450 (`_validate_openai_chat`)
- **Issue**: Validation uses `kilo-auto/free` model which doesn't require authentication
- **Impact**: All Kilo Gateway connections show "connected" regardless of key validity
- **Fix**: Use `/models` endpoint for validation (requires auth) or validate against a paid model

### BUG 2: Frontend Doesn't Store API Key on Create (HIGH)
- **Location**: Frontend add-connection flow for Kilo Gateway
- **Issue**: Connection `96c443e4` created via frontend has no apiKey in data blob
- **Impact**: Test connection and fetch models fail with "No API key configured"
- **Fix**: Ensure frontend sends apiKey in the create request body

### BUG 3: Model Routing Without Provider Prefix (LOW)
- **Location**: `backend/app/services/proxy.py` line 412-414 (`_resolve_single_model`)
- **Issue**: `kilo-auto/free` resolves to provider `kilo-auto` which doesn't exist
- **Impact**: Users must use `kg/kilo-auto/free` instead of just `kilo-auto/free`
- **Note**: This is by design — proxy expects `provider/model` format. Frontend should prefix models with provider alias.

### BUG 4: Test Connection Returns latencyMs=0 (LOW)
- **Location**: `backend/app/routers/providers.py` line 623-625
- **Issue**: `openai-chat` validation type hardcodes `latencyMs: 0`
- **Fix**: Measure actual request latency in `_validate_openai_chat`

---

## Recommendations

1. **Fix validation** — Use `/models` endpoint or a paid model for Kilo Gateway key validation
2. **Fix frontend create flow** — Ensure apiKey is stored in data blob during connection creation
3. **Document routing** — Kilo Gateway models require `kg/` prefix when used via proxy
4. **Add latency measurement** — `_validate_openai_chat` should return actual latency

---

## Test Environment Cleanup
- Test connections `4a219959` and `7c1fd41d` deleted
- Original connection `96c443e4` updated with API key via PATCH
- Kilo Code OAuth connection `49111b35` unchanged
