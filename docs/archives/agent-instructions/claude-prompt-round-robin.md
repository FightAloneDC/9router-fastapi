Read these plan docs first, then implement ALL phases:
- `docs/plans/round-robin-implementation.md`
- `docs/reference/combo-system.md`

## Summary of What Needs to Change

The FastAPI proxy currently has a **shell** for round-robin but no real logic. Here's exactly what's wrong and what to fix:

### Current State (broken)
1. `_build_target_for_provider()` in `proxy.py:528` loops ALL connections and returns ALL of them. Should return **ONE** selected connection.
2. `chat_completions()` in `v1_proxy.py:90` does `for target in targets` — simple iteration with no retry/exclude logic. Should be `while True` loop with `exclude_connection_ids`.
3. `_get_rotated_targets()` in `v1_proxy.py:71` does **sequential** rotation (A→B→C→A→B→C). Must use **random jitter** (A→A→B→A→C→B) for anti-ban.
4. `_should_fallback_on_error()` in `v1_proxy.py:53` only checks 5xx + 429. Needs text-based matching ("rate limit", "quota exceeded", etc.) + more status codes (401, 402, 403, 404).
5. No cooldown system — retries hit the same failing connection immediately.
6. No model lock — a connection that fails for model X still gets tried for model X.
7. No connection cache — DB query on every single request.
8. Per-provider strategy exists in settings but proxy never reads it.

### Implementation Order (6 phases)

**Phase 1: Connection-Level Round Robin** (most impactful)
- Add `lastUsedAt`, `consecutiveUseCount` fields to connection data blob (JSON, NOT new DB columns)
- Create `select_connection_for_provider()` in `proxy.py` with 3 strategies: fill-first, round-robin (random jitter), random
- Refactor `_build_target_for_provider()` to use `select_connection_for_provider()` — return 1 target, not all
- Refactor fallback loop in `chat_completions()` to `while True` with `exclude_connection_ids`

**Phase 2: Cooldown System**
- Create `backend/app/services/account_fallback.py` with:
  - Error rules (text-based: "rate limit", "quota exceeded", "capacity", "overloaded" → backoff; status-based: 401/402/403/404 → 120s, 429 → backoff)
  - Exponential backoff: base=2s, max=5min, formula: min(base * 2^(level-1), max)
  - `is_rate_limited()`, `is_model_lock_active()`, `calculate_cooldown()`, `build_cooldown_update()`, `build_clear_cooldown_update()`
- Add `mark_connection_unavailable()` to `proxy.py` (write to DB ONLY on error)
- Add `clear_connection_error()` to `proxy.py` (write to DB on success)

**Phase 3: Model Lock**
- Add `modelLock_<model>` fields to connection data
- Set model lock when request fails (cooldown per model)
- Clear model lock when request succeeds
- Filter model-locked connections in `select_connection_for_provider()`

**Phase 4: Per-Provider Strategy Override**
- Read `providerStrategies[providerId]` from settings, fallback to global `comboStrategy`
- Update `select_connection_for_provider()` to use per-provider strategy
- Add UI dropdown in `ProviderDetailPage.jsx` for per-provider strategy

**Phase 5: Combo-Level Rotation Fix**
- Fix `_get_rotated_targets()` to use random jitter (same anti-ban pattern as connection-level)
- Support per-combo strategy from `comboStrategies[comboName]` in settings
- Add UI in ComboFormModal for per-combo strategy

**Phase 6: Testing & Verification**
- Test 1 provider, 1 connection → fill-first (unchanged)
- Test 1 provider, 3 connections, round-robin → rotate with sticky
- Test connection error → cooldown → skip, retry next
- Test per-provider strategy override
- Test combo + connection rotation together

### Critical Rules
- Do NOT add new DB columns. All new fields go in the JSON `data` blob of ProviderConnection.
- Use random rotation, NOT sequential. Sequential pattern (A→B→C→A→B→C) is easily detected as abuse.
- DB writes happen ONLY on error (cooldown/mark unavailable) and success (clear error). NOT on every request.
- Reference original Node.js files in `~/dev/9router/` for exact behavior:
  - `src/sse/services/auth.js` — connection selection
  - `open-sse/services/combo.js` — combo rotation
  - `open-sse/services/accountFallback.js` — cooldown/backoff
  - `open-sse/config/errorConfig.js` — error rules

Start with Phase 1 and work through all phases sequentially. After each phase, verify the changes compile and the logic is correct before moving on.
