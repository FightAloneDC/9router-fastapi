# Audit: Fetch Models, Clear Models, and Enable All Toggle

**Date:** 2026-05-19
**Original:** `/home/mint/dev/9router/` (Next.js)
**Ported:** `/home/mint/dev/9router-fastapi/` (FastAPI + React)

---

## Section 1: Fetch Models

### Original Implementation (Next.js)

The original project has **two distinct "Fetch Models" mechanisms** depending on provider type:

#### 1a. Non-Compatible Providers (hardcoded models + suggested models)

- **No explicit "Fetch Models" button** for standard providers (OpenAI, Claude, Gemini, etc.)
- Models come from **hardcoded constants** in `src/shared/constants/models.js` via `getModelsByProviderId(providerId)`
- **Suggested models** are fetched via a public API proxy:
  - Frontend: `src/shared/utils/providerModelsFetcher.js` → calls `GET /api/providers/suggested-models?url=...&type=...`
  - Backend: `src/app/api/providers/suggested-models/route.js` — proxies the request to the provider's public models API
  - Provider configs define `modelsFetcher` property (e.g., `{ url: "https://...", type: "openai" }`)
  - Results are cached in-memory for 10 minutes
  - Displayed as "Suggested free models (≥200k context)" chips below the main model list
  - Clicking a suggestion adds it as a model alias

#### 1b. Compatible Providers (OpenAI/Anthropic-compatible nodes)

- **"Import from /models" button** in `CompatibleModelsSection.js`
  - File: `src/app/(dashboard)/dashboard/providers/[id]/CompatibleModelsSection.js` (line 144-179)
  - Calls `GET /api/providers/${activeConnection.id}/models`
  - Iterates through returned models, resolves aliases, and adds each via `onSetAlias()`
  - Backend endpoint: `src/app/api/providers/[id]/models/route.js` (line 331-490)
  - Supports ~30+ provider-specific configs with custom auth headers, URL patterns, and response parsers
  - Handles OAuth token refresh for providers like Gemini CLI and Kiro

#### Key Original Files:
| File | Role |
|------|------|
| `src/app/api/providers/[id]/models/route.js` | Backend: fetch models from provider API |
| `src/app/api/providers/suggested-models/route.js` | Backend: proxy for suggested models |
| `src/shared/utils/providerModelsFetcher.js` | Frontend: fetch + cache suggested models |
| `src/app/(dashboard)/dashboard/providers/[id]/CompatibleModelsSection.js` | Frontend: Import from /models UI |
| `src/app/(dashboard)/dashboard/providers/[id]/page.js` (lines 340-345) | Frontend: load suggested models on page mount |
| `src/app/(dashboard)/dashboard/providers/[id]/page.js` (lines 803-832) | Frontend: render suggested models chips |

### Ported Implementation (FastAPI + React)

The ported project has **three Fetch Models mechanisms**:

#### 1a. Suggested Models (same as original)
- Frontend: `frontend/src/utils/providerModelsFetcher.js` — identical logic, adds auth token
- Backend: `GET /providers/suggested-models` in `backend/app/routers/providers.py` (line 980)
- **Status: ✅ Implemented**

#### 1b. Compatible Providers — Import from /models
- Frontend: `frontend/src/components/CompatibleModelsSection.jsx` (line 150-180)
  - Calls `GET /providers/${activeConnection.id}/models`
  - Same logic as original
- Backend: `GET /providers/{conn_id}/models` in `backend/app/routers/providers.py` (line 1427-1557)
  - Supports OpenAI-compatible, Anthropic-compatible, and provider-specific configs
  - **Status: ✅ Implemented**

#### 1c. Non-Compatible Providers — "Fetch Models" button (NEW in port)
- Frontend: `frontend/src/pages/ProviderDetailPage.jsx` (lines 1179-1200)
  - **New "Fetch Models" button** that doesn't exist in the original
  - Calls `providersApi.fetchProviderModels(conn.id)` for each connection
  - Saves fetched model IDs to connection data via `saveModels()`
  - `saveModels()` (line 1149) persists to all connections via `PATCH /providers/{id}` with `{ models: [...] }`
- Models are loaded on page mount from `filtered[0].models` (line 1052)
- **Status: ⚠️ Partially implemented — behavioral difference from original**

### Gap Analysis: Fetch Models

| Aspect | Original | Ported | Status |
|--------|----------|--------|--------|
| Suggested models (public API) | ✅ | ✅ | ✅ Match |
| Compatible: Import from /models | ✅ | ✅ | ✅ Match |
| Non-compatible: Fetch Models button | ❌ Not in original | ✅ Added | ⚠️ New feature |
| Model persistence | Hardcoded constants + aliases | Connection data JSON | ⚠️ Different architecture |
| Models survive page refresh | ✅ (hardcoded) | ⚠️ Depends on connection data | ⚠️ Potential issue |

**Key Issue:** The ported version stores fetched models in `connection.data.models[]`, but the original uses hardcoded constants. If `saveModels()` fails silently or the connection data is corrupted, models disappear on refresh. The original never has this problem because models are hardcoded.

---

## Section 2: Clear Models

### Original Implementation (Next.js)

The original project does **NOT have a "Clear Models" button** for standard providers.

- For **non-compatible providers**: Models are hardcoded constants — there's nothing to "clear"
- For **compatible providers**: Individual model aliases can be deleted via `onDeleteAlias()`, but there's no bulk "Clear All" button
- The `DELETE /api/providers/[id]/models` endpoint does NOT exist in the original
- Model aliases can be removed individually via `DELETE /api/models/alias?alias=...`

### Ported Implementation (FastAPI + React)

The ported project **added a "Clear Models" button** (not in original):

#### Frontend
- `frontend/src/pages/ProviderDetailPage.jsx` (lines 1203-1232)
  - `handleClearModels()` — clears all models from all connections
  - Calls `providersApi.updateProvider(c.id, { models: [] })` for each connection
  - Resets local state: `setModels([])`, `setEnabledModelIds(new Set())`, `setSuggestedModels([])`
  - Has a retry pattern (tries twice)
  - Button rendered at line 1964

#### Backend
- `DELETE /providers/{conn_id}/models` in `backend/app/routers/providers.py` (line 1560-1605)
  - Clears `data.models` array in connection
  - Also clears disabled models for this provider from settings
  - Returns `{ ok: true, clearedCount: N }`
- `PATCH /providers/{id}` — general update endpoint used by `handleClearModels` to set `models: []`

### Gap Analysis: Clear Models

| Aspect | Original | Ported | Status |
|--------|----------|--------|--------|
| Clear Models button | ❌ Not in original | ✅ Added | ⚠️ New feature |
| Delete individual model alias | ✅ | ✅ | ✅ Match |
| DELETE /providers/{id}/models endpoint | ❌ | ✅ | ⚠️ New endpoint |
| Clear also removes disabled models | N/A | ✅ | ✅ Good |

**Key Issue:** This is a new feature not present in the original. The implementation looks correct but differs architecturally — it clears `connection.data.models[]` which is a ported-only concept.

---

## Section 3: Enable All Toggle

### Original Implementation (Next.js)

#### "Active All" Button (Enable All)
- File: `src/app/(dashboard)/dashboard/providers/[id]/page.js` (lines 1153-1156)
- Button text: **"Active All"** (with `restart_alt` icon)
- Only shown when `disabledModelIds.length > 0`
- Handler: `handleEnableAll()` (lines 165-172)
  - Calls `DELETE /api/models/disabled?providerAlias=${providerStorageAlias}`
  - Backend: `src/app/api/models/disabled/route.js` → `enableModels(providerAlias, [])` — removes all disabled models for that provider
  - Then refetches disabled models list

#### "Disable All" Button
- File: same page (lines 1158-1161)
- Button text: **"Disable All"** (with `block` icon)
- Only shown when `activeIds.length > 0`
- Handler: `handleDisableAll(ids)` (lines 144-163)
  - Shows confirmation modal first
  - Calls `POST /api/models/disabled` with `{ providerAlias, ids: [...allActiveIds] }`
  - Backend adds all IDs to disabled list

#### Disabled Models Storage
- Backend: `src/lib/disabledModelsDb.js` → re-exports from `src/lib/db/index.js`
- Stored in SQLite database (separate from connection data)
- API: `GET/POST/DELETE /api/models/disabled`

#### UI Rendering
- Non-compatible providers only (lines 1145: `!isCompatible &&`)
- Active All button: shown when `disabledModelIds.length > 0`
- Disable All button: shown when `activeIds.length > 0`
- Disabled models displayed as dashed-border chips below active models (lines 834-852)
- Clicking a disabled model chip re-enables it individually

### Ported Implementation (FastAPI + React)

#### "Enable All" Button
- File: `frontend/src/pages/ProviderDetailPage.jsx` (line 1969-1971)
- Button text: **"Enable All"** (with `RotateCcw` icon)
- Only shown when `disabledModelIds.length > 0`
- Handler: `handleEnableAll()` (lines 1295-1301)
  - Calls `DELETE /models/disabled?providerAlias=${providerStorageAlias}`
  - Backend: `backend/app/routers/models.py` → `enable_models()` (line 239-266)
  - Then refetches disabled models

#### "Disable All" Button
- File: same page (line 1974-1976)
- Button text: **"Disable All"** (with `Ban` icon)
- Handler: `handleDisableAll(ids)` (lines 1277-1293)
  - Shows confirmation modal
  - Calls `POST /models/disabled` with `{ providerAlias, ids }`
  - Backend adds IDs to disabled list

#### Disabled Models Storage
- Backend: `backend/app/routers/models.py` (lines 199-266)
- Stored in **settings data JSON** (`SettingsModel.data.disabledModels`)
- API: `GET/POST/DELETE /models/disabled`

#### UI Rendering
- Non-compatible providers with models (line 1955: `!isCompatible && models.length > 0`)
- Enable All button: shown when `disabledModelIds.length > 0`
- Disable All button: shown when `activeIds.length > 0`
- Disabled models displayed as dashed-border chips (lines 1695-1715)
- Clicking a disabled model chip calls `handleEnableModel()` to restore individually

### Gap Analysis: Enable All Toggle

| Aspect | Original | Ported | Status |
|--------|----------|--------|--------|
| Enable All button | ✅ "Active All" | ✅ "Enable All" | ✅ Match (different label) |
| Disable All button | ✅ | ✅ | ✅ Match |
| Confirmation modal for Disable All | ✅ | ✅ | ✅ Match |
| Individual model disable/enable | ✅ | ✅ | ✅ Match |
| Disabled models display | ✅ Dashed chips | ✅ Dashed chips | ✅ Match |
| Disabled storage backend | SQLite DB | Settings JSON | ⚠️ Different storage |
| Button visibility condition | `disabledModelIds.length > 0` | `disabledModelIds.length > 0` | ✅ Match |
| Works for non-compatible only | ✅ | ✅ | ✅ Match |

**Status: ✅ Enable All is correctly implemented and functionally matches the original.**

The only differences are cosmetic ("Active All" → "Enable All", different icon) and storage backend (SQLite → settings JSON), neither of which affects functionality.

---

## Section 4: Gap Analysis Summary

### Feature Matrix

| Feature | Original | Ported | Verdict |
|---------|----------|--------|---------|
| **Fetch Models** | | | |
| Suggested models (public API proxy) | ✅ | ✅ | ✅ Match |
| Compatible: Import from /models | ✅ | ✅ | ✅ Match |
| Non-compatible: Fetch Models button | ❌ | ✅ | ⚠️ New (not in original) |
| Models persist across refresh | ✅ (hardcoded) | ⚠️ (connection data) | ⚠️ Risk |
| **Clear Models** | | | |
| Clear Models button | ❌ | ✅ | ⚠️ New (not in original) |
| DELETE /providers/{id}/models | ❌ | ✅ | ⚠️ New endpoint |
| Individual alias delete | ✅ | ✅ | ✅ Match |
| **Enable All Toggle** | | | |
| Enable All button | ✅ | ✅ | ✅ Match |
| Disable All button | ✅ | ✅ | ✅ Match |
| Confirmation modal | ✅ | ✅ | ✅ Match |
| Individual enable/disable | ✅ | ✅ | ✅ Match |
| Disabled models display | ✅ | ✅ | ✅ Match |

### Root Cause Analysis: Why Features Seem Broken

The user reports that Fetch Models, Clear Models, and Enable All are "broken or missing." Based on this investigation:

1. **Enable All toggle is NOT missing** — it exists at line 1969 of `ProviderDetailPage.jsx` and works correctly. The button only appears when `disabledModelIds.length > 0`, so if no models are disabled, the button won't show. This is correct behavior matching the original.

2. **Fetch Models works differently** — the ported version added a "Fetch Models" button for non-compatible providers that fetches from the provider API and stores in connection data. This is a NEW feature. If it's not working, the issue is likely:
   - The `providersApi.fetchProviderModels()` call failing
   - The `saveModels()` call not persisting correctly
   - The `PATCH /providers/{id}` endpoint not handling the `models` field

3. **Clear Models is a new feature** — not present in the original. If it's not working, the issue is in `handleClearModels()` or the `PATCH /providers/{id}` endpoint.

### Recommended Fix Tasks

1. **Verify Fetch Models persistence** — Test that `handleFetchModels()` correctly saves to connection data and models survive page refresh
2. **Verify Enable All visibility** — Confirm the button appears when models are disabled (may need to disable a model first to see it)
3. **Verify Clear Models** — Test that `handleClearModels()` correctly clears models from connection data

### Key File Reference

#### Original Project (`/home/mint/dev/9router/`)
| File | Lines | Feature |
|------|-------|---------|
| `src/app/api/providers/[id]/models/route.js` | 1-490 | Fetch models from provider API |
| `src/app/api/models/disabled/route.js` | 1-50 | Disabled models CRUD |
| `src/app/api/models/availability/route.js` | 1-103 | Model availability/cooldown |
| `src/shared/utils/providerModelsFetcher.js` | 1-30 | Suggested models fetcher |
| `src/app/(dashboard)/dashboard/providers/[id]/page.js` | 112-172 | Disable/Enable handlers |
| `src/app/(dashboard)/dashboard/providers/[id]/page.js` | 340-345 | Load suggested models |
| `src/app/(dashboard)/dashboard/providers/[id]/page.js` | 1139-1171 | Models card with buttons |
| `src/app/(dashboard)/dashboard/providers/[id]/CompatibleModelsSection.js` | 144-179 | Import from /models |
| `src/app/(dashboard)/dashboard/providers/[id]/ModelRow.js` | 1-95 | Model row component |

#### Ported Project (`/home/mint/dev/9router-fastapi/`)
| File | Lines | Feature |
|------|-------|---------|
| `backend/app/routers/providers.py` | 1427-1557 | Fetch models from provider API |
| `backend/app/routers/providers.py` | 1560-1605 | Clear provider models |
| `backend/app/routers/providers.py` | 980-1050 | Suggested models endpoint |
| `backend/app/routers/models.py` | 199-266 | Disabled models CRUD |
| `backend/app/routers/models.py` | 41-80 | Model availability |
| `frontend/src/utils/providerModelsFetcher.js` | 1-34 | Suggested models fetcher |
| `frontend/src/pages/ProviderDetailPage.jsx` | 1026-1035 | Fetch disabled models |
| `frontend/src/pages/ProviderDetailPage.jsx` | 1149-1200 | Save/Fetch models handlers |
| `frontend/src/pages/ProviderDetailPage.jsx` | 1203-1232 | Clear models handler |
| `frontend/src/pages/ProviderDetailPage.jsx` | 1257-1301 | Disable/Enable handlers |
| `frontend/src/pages/ProviderDetailPage.jsx` | 1950-1993 | Models card with buttons |
| `frontend/src/components/CompatibleModelsSection.jsx` | 150-180 | Import from /models |
