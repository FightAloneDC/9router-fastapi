# QA Report: Fetch Models Persistence Re-verification

**Date:** 2026-05-19
**Task:** t_d35ce8c3 — Re-QA: Verify Fetch Models persistence after backend fix
**Backend:** http://localhost:9000
**Tester:** 9router-qa

## Background

Previous QA (t_5524b7b4) found a CRITICAL bug: `GET /providers/{id}/models` fetched models from the provider API but did NOT persist them to the database. This re-verification confirms the backend fix.

## Test Results

### Test 1: Fetch Models Persistence (kilo-gateway)
- **Provider:** QA Test Key (kilo-gateway, 344 models)
- **Endpoint:** GET /providers/{id}/models
- **Steps:**
  1. Clear models → clearedCount: 344 ✓
  2. Fetch models → 344 models returned ✓
  3. Verify via GET /providers/{id} → 344 models stored ✓
- **Status:** ✅ PASS

### Test 2: Fetch Models Persistence (nvidia)
- **Provider:** hanawatibafasari@enowgntg.com (nvidia, 119→125 models)
- **Endpoint:** GET /providers/{id}/models
- **Steps:**
  1. Clear models → clearedCount: 119 ✓
  2. Fetch models → 125 models returned ✓
  3. Verify via GET /providers/{id} → 125 models stored ✓
- **Status:** ✅ PASS

### Test 3: Fetch Models Persistence (cerebras)
- **Provider:** GaramanRarali@enowxai.site (cerebras, 4 models)
- **Steps:**
  1. Fetch models → 4 models returned ✓
  2. Verify → 4 models stored ✓
- **Status:** ✅ PASS

### Test 4: Clear Models
- **Providers tested:** kilo-gateway, nvidia, cerebras
- **Endpoint:** DELETE /providers/{id}/models
- **Steps:**
  1. DELETE → `{"ok": true, "clearedCount": N}` ✓
  2. Verify via GET /providers/{id} → models: [] ✓
- **Status:** ✅ PASS

### Test 5: Fetch After Clear
- **Providers tested:** kilo-gateway (344 models), nvidia (125 models)
- **Steps:**
  1. Clear models ✓
  2. Fetch models → models returned ✓
  3. Verify persistence → models stored ✓
- **Status:** ✅ PASS

### Test 6: Enable/Disable Models
- **Endpoint:** POST /models/disabled (disable), DELETE /models/disabled (enable)
- **Provider:** cerebras (3 test models)
- **Steps:**
  1. POST with `{"ids": [...], "providerAlias": "cerebras"}` → `{"success": true}` ✓
  2. GET /models/disabled → models appear in disabled list ✓
  3. DELETE with query params `?providerAlias=cerebras&id=X` → `{"success": true}` ✓
  4. Verify → models removed from disabled list ✓
- **Status:** ✅ PASS
- **Note:** DELETE /models/disabled requires query params, not body. Body-based DELETE returns `"providerAlias required"`.

## Summary

| Test | Status |
|------|--------|
| Fetch persistence (kilo-gateway) | ✅ PASS |
| Fetch persistence (nvidia) | ✅ PASS |
| Fetch persistence (cerebras) | ✅ PASS |
| Clear models | ✅ PASS |
| Fetch after clear | ✅ PASS |
| Enable/disable models | ✅ PASS |

**Total: 6 tests, 6 passed, 0 failed**

## Acceptance Criteria

- [x] Fetch models persistence: after fetching, GET /providers/{id} includes a non-empty models list
- [x] This holds for two different provider types (kilo-gateway + nvidia + cerebras)
- [x] Clear models: after clearing, models list is empty
- [x] Fetch after Clear: models are populated again

## API Calls Used: ~25 (under 30 limit)

## Minor Observation

DELETE /models/disabled only accepts query parameters (`?providerAlias=X&id=Y`), not JSON body. This is consistent REST behavior but differs from POST which accepts body. Not a bug — just a note for API consumers.
