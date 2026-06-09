# Audit Report: Provider Restructuring Verification

**Date**: 2026-05-21
**Audit ID**: t_f00719a3
**Auditor**: 9router-docs (compiled from 4 verification tasks)
**Project**: 9router-fastapi
**Reference**: Original Next.js at `/home/mint/dev/9router/src`

---

## Executive Summary

This report compiles findings from four verification audits of the provider
restructuring implementation. The audit covers serviceKinds mapping, model type
regex detection, API endpoint contracts, and model storage/override mechanisms.

**Overall Verdict: FAIL — 36 findings across 4 verification areas.**

| Severity | Count | Description |
|----------|-------|-------------|
| P0       | 2     | Critical — broken functionality |
| P1       | 16    | Important — missing/incorrect behavior |
| P2       | 18    | Minor — nice-to-have, cosmetic, or future |
| **Total**| **36**| |

---

## Severity Definitions

- **P0 — Critical**: Feature is broken. Provider connections fail, models
  cannot be resolved, or core routing is non-functional.
- **P1 — Important**: Feature works partially but with incorrect behavior.
  Missing kinds cause providers to appear/disappear from wrong tabs. Missing
  endpoints block planned functionality.
- **P2 — Minor**: Cosmetic differences, missing UI polish, or future features
  not yet needed. Does not affect core functionality.

---

## Section 1: serviceKinds Verification

**Source task**: t_1594051f
**Full audit**: `audit-serviceKinds.md` (in workspace)
**Source of truth**: `/home/mint/dev/9router/src/shared/constants/providers.js`

### Summary

- Providers checked: ~80+ (active, non-commented)
- Providers with explicit serviceKinds in original: 38
- Providers defaulting to ["llm"] in original: ~40+
- Findings: 21 total (2 P0, 9 P1, 5 P2, plus 5 P1 from missing providers)

### P0 — Critical (2 findings)

#### Finding 1: OpenRouter missing "tts" in backend + frontend

- **Files**: `backend/app/routers/providers/constants.py` line 16,
  `frontend/src/constants/providers.js`
- **Current**: `[\"llm\", \"embedding\", \"imageToText\"]`
- **Expected**: `[\"llm\", \"embedding\", \"tts\", \"imageToText\"]`
- **Impact**: TTS requests routed through OpenRouter will not be recognized as
  valid on the backend. Frontend also missing from TTS tab.

#### Finding 2: Backend uses wrong key "assemblyai-stt" instead of "assemblyai"

- **File**: `backend/app/routers/providers/constants.py` line 96
- **Current**: Key is `"assemblyai-stt"` with `serviceKinds: ["stt"]`
- **Expected**: Key should be `"assemblyai"` with `serviceKinds: ["stt"]`
- **Impact**: AssemblyAI connections created by users with `provider_id="assemblyai"`
  will fail to resolve in the backend config lookup. Provider is completely broken.

### P1 — Frontend serviceKinds Mismatches (8 findings)

| # | Provider | Current (FE) | Expected | Missing |
|---|----------|-------------|----------|---------|
| 3 | anthropic | `["llm"]` | `["llm", "imageToText"]` | imageToText |
| 4 | groq | `["llm", "stt"]` | `["llm", "imageToText", "stt"]` | imageToText |
| 6 | mistral | `["llm", "embedding"]` | `["llm", "imageToText", "embedding"]` | imageToText |
| 7 | perplexity | `["llm"]` | `["llm", "webSearch"]` | webSearch |
| 8 | huggingface | `["llm", "embedding", "image"]` | `["image", "imageToText", "tts", "stt"]` | Wrong entirely |
| 10 | together | `["llm", "embedding", "image"]` | `["llm", "embedding"]` | Extra "image" |
| 13 | cohere | `["llm", "embedding"]` | `["llm"]` (default) | Extra "embedding" |

### P1 — Missing Providers (13 providers)

These providers exist in the original but are missing from both backend and
frontend in the FastAPI port:

| Provider | serviceKinds | Category |
|----------|-------------|----------|
| commandcode | `["llm"]` (default) | APIKEY_PROVIDERS |
| blackbox | `["llm"]` | APIKEY_PROVIDERS |
| chutes | `["llm"]` (default) | APIKEY_PROVIDERS |
| aws-polly | `["tts"]` | APIKEY_PROVIDERS |
| google-pse | `["webSearch"]` | APIKEY_PROVIDERS |
| linkup | `["webSearch"]` | APIKEY_PROVIDERS |
| searchapi | `["webSearch"]` | APIKEY_PROVIDERS |
| youcom | `["webSearch"]` | APIKEY_PROVIDERS |
| jina-reader | `["webFetch"]` | APIKEY_PROVIDERS |
| topaz | `["image"]` | APIKEY_PROVIDERS |
| runwayml | `["image", "video"]` | APIKEY_PROVIDERS |
| recraft | `["image"]` | APIKEY_PROVIDERS |
| black-forest-labs | `["image"]` | APIKEY_PROVIDERS |

### P2 — Minor (5 findings)

| # | Finding | Notes |
|---|---------|-------|
| 17 | Frontend has "volcengine" not in original | May be intentional addition |
| 18 | Frontend has "kilo-gateway" not in original | Likely intentional |
| 19 | Frontend has "askcodi" not in original | Likely intentional |
| 20 | Frontend has "amazon-bedrock" not in original | Likely intentional |
| 21 | `getProvidersByKind()` missing `hiddenKinds` filter | Providers with hiddenKinds appear in wrong tabs |

### Full Comparison Table

See `audit-serviceKinds.md` for the complete 40+ row comparison table covering
every provider with explicit serviceKinds in the original.

---

## Section 2: Model Type Regex Verification

**Source task**: t_ed8f5a37
**Source of truth**: `/home/mint/dev/9router/src/app/api/v1/models/route.js`
**Implementation**: `backend/app/routers/providers/constants.py`

### Summary

- TTS regex: **MATCH** ✅
- Default regex: **MATCH** ✅
- Override order: **MATCH** ✅
- Findings: 3 total (2 P1, 1 P2)

### P1 — Regex Divergences (2 findings)

#### Finding 1: Embedding regex expanded from 1 to 7 patterns

- **File**: `backend/app/routers/providers/constants.py` line 226
- **Current**: `embed|e5-|bge-|gte-|nomic|cohere-embed|voyage-`
- **Original**: Single `/embed/.test(lower)` pattern
- **Impact**: New models matching the additional patterns (e5-, bge-, gte-,
  nomic, cohere-embed, voyage-) will be auto-classified as embedding in the
  FastAPI port but NOT in the original. The MODEL_TYPE_OVERRIDES dict partially
  mitigates this for known models, but new/unlisted models would behave
  differently.

#### Finding 2: STT category added (not in original)

- **File**: `backend/app/routers/providers/constants.py` line 234
- **Current**: `whisper|transcri|stt|asr` regex for STT detection
- **Original**: NO STT regex detection — STT models only detected via
  `staticModelKindById` map (a curated list)
- **Impact**: Any model with "whisper", "transcri", "stt", or "asr" in its name
  will be auto-classified as STT. In the original, only explicitly listed STT
  models (whisper-1, etc.) were recognized.

### P2 — Minor Regex Differences (1 finding)

#### Finding 3: Image regex adds "midjourney" not in original

- **File**: `backend/app/routers/providers/constants.py` line 238
- **Current**: Adds `midjourney` to image detection
- **Original**: `image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion`
- **Impact**: Models containing "midjourney" in name auto-classified as image
  type. Unlikely to cause issues in practice.

### Positive Findings ✅

- TTS regex matches exactly
- Default regex matches exactly
- MODEL_TYPE_OVERRIDES checked before regex (same order as original)

---

## Section 3: API Endpoints & Kind Filtering

**Source task**: t_ce14cc8b

### Summary

- Findings: 6 total (2 P1, 4 P2)

### P1 — Endpoints (2 findings)

#### Finding 1: ~30 providers have wrong serviceKinds in frontend constants

- **File**: `frontend/src/constants/providers.js`
- **Issue**: Frontend constants have wrong serviceKinds for ~30 providers,
  causing the Media Providers page to show/hide providers in wrong tabs.
- **Impact**: Media Providers page is unreliable — users see incorrect provider
  listings per tab.
- **Cross-reference**: This is the same class of issue as Section 1's frontend
  mismatches, but audited independently from the endpoint/filtering perspective.

#### Finding 2: ProvidersPage doesn't filter out non-LLM providers

- **File**: `frontend/src/pages/ProvidersPage.jsx`
- **Issue**: The main Providers page shows ALL providers, including media-only
  providers like elevenlabs (TTS), assemblyai (STT), etc. The original filters
  to only show providers with "llm" in serviceKinds.
- **Impact**: Users see irrelevant media-only providers on the main LLM
  providers page.

### P2 — Endpoints (4 findings)

| # | File | Issue |
|---|------|-------|
| 3 | `backend/app/schemas/provider.py` | `ProviderConnectionOut` schema missing `serviceKinds` — silently stripped from GET /providers response |
| 4 | `backend/app/routers/providers/helpers.py` | GET /providers/client returns `serviceKinds` but original's equivalent does not |
| 5 | `backend/app/routers/providers/connections.py` | GET /providers returns bare array; original returns wrapped `{connections: [...]}` |
| 6 | `backend/app/routers/v1_proxy.py` | Missing `/v1/models/{kind}` endpoint for kind-filtered model listing |

---

## Section 4: Model Storage & User Type Override

**Source task**: t_acb22871
**Full audit**: `audit-model-storage-and-user-override.md` (in workspace)
**Overall verdict**: **FAIL** — Schema mismatch blocks core model type feature.

### Summary

- Findings: 6 total (3 P1, 3 P2)
- Follow-up tasks created: t_2672b60a (backend fix), t_052e2a36 (frontend UI)

### P1 — Model Storage (3 findings)

#### Finding 1: Schema `models: list[str]` blocks `{id, type}` storage

- **Files**: `backend/app/schemas/provider.py` lines 23, 45, 84
- **Issue**: All three schemas (`ProviderConnectionCreate`,
  `ProviderConnectionUpdate`, `ProviderConnectionOut`) define `models` as
  `list[str]`. Pydantic rejects `[{id: "gpt-4o", type: "llm"}]` objects.
- **Expected**: Schemas should accept both `list[str]` (backward compat) and
  `list[dict]` with `{id, type}`.
- **Fix**: Change to `list[Union[str, ModelEntry]]` where `ModelEntry` has
  `id: str` and `type: str = "llm"`.

#### Finding 2: `PATCH /providers/{conn_id}/models/type` endpoint NOT implemented

- **Location**: `backend/app/routers/providers/` — no matching route
- **Issue**: Plan task 9 explicitly calls for this endpoint. It does not exist.
  There is no way for users to override a model's type (e.g., change from "llm"
  to "embedding").
- **Fix**: Implement endpoint accepting `{ model_id: str, type: str }` body.

#### Finding 3: `fetch_provider_models` discards type info on storage

- **Files**: `backend/app/routers/providers/models.py` lines 450, 480, 505
- **Issue**: After fetching models, code stores only `[m["id"] for m in models]`
  — plain string IDs. Type information from `_normalize_model()` is lost.
- **Expected**: Store as `[{id, type}]` objects per plan task 4.
- **Fix**: Change to `[{"id": m["id"], "type": m["type"]} for m in models]` in
  all three code paths (OpenAI-compatible, Anthropic-compatible, generic).

### P2 — Model Storage (3 findings)

| # | File | Issue |
|---|------|-------|
| 4 | `helpers.py:63`, `connections.py:319-320` | `normalize_models_list` called on read but NOT on write — inconsistent stored format |
| 5 | `constants.py:245-260` | No mechanism for storing user type overrides separately from auto-detected types |
| 6 | `ProviderDetailPage.jsx:1052-1744` | Frontend has defensive `typeof` code but no type override UI (plan task 13) |

### Cross-reference: Original Behavior

The original Next.js codebase:
- Stores models as plain string IDs (same as FastAPI port)
- Has separate `customModels` KV store with `{providerAlias, id, type}` format
- Uses `PROVIDER_MODELS` constant with `{id, type}` static definitions
- Does NOT have a user model type override feature (plan adds this as new)

---

## Section 5: Cross-cutting Issues

### 5.1 Frontend ↔ Backend serviceKinds Drift

The most pervasive issue is frontend constants having different serviceKinds
than the backend. This means:
- Backend validates one set of kinds
- Frontend displays providers in different tabs
- Users see inconsistent behavior between what the API allows and what the UI
  shows

**Affected providers** (frontend wrong, backend correct):
anthropic, groq, mistral, perplexity, huggingface, together, cohere, xai

### 5.2 Missing Provider Coverage Gap

13 providers from the original are missing from BOTH backend and frontend.
This is a coverage gap — these providers simply don't exist in the FastAPI port.
Users cannot connect to: commandcode, blackbox, chutes, aws-polly, google-pse,
linkup, searchapi, youcom, jina-reader, topaz, runwayml, recraft,
black-forest-labs.

### 5.3 Model Type Pipeline Incompleteness

The model type system has three layers:
1. **Provider-level** (serviceKinds) — which service types a provider supports
2. **Model-level** (type) — which type each model is (llm, embedding, tts, etc.)
3. **User override** — ability to change a model's type

Layer 1 is partially working (with mismatches documented above).
Layer 2 is broken at the storage level (schemas reject dict objects).
Layer 3 is not implemented (endpoint missing).

---

## Prioritized Fix Recommendations

### Immediate (P0 — fix now)

1. **Fix OpenRouter "tts"** — Add `"tts"` to OpenRouter serviceKinds in both
   backend constants.py and frontend providers.js.
2. **Fix assemblyai key** — Rename `"assemblyai-stt"` to `"assemblyai"` in
   backend constants.py.

### High Priority (P1 — fix soon)

3. **Fix all frontend serviceKinds mismatches** — 8 providers need frontend
   corrections (see Section 1, P1 table).
4. **Implement `PATCH /providers/{conn_id}/models/type`** endpoint.
5. **Fix model storage schemas** — Change `list[str]` to accept `list[Union[str, dict]]`.
6. **Fix `fetch_provider_models`** to store `{id, type}` objects instead of
   plain strings.
7. **Filter ProvidersPage** to only show LLM providers.

### Medium Priority (P2 — fix when available)

8. Add missing providers (13 total) to both backend and frontend.
9. Add `normalize_models_list` on write paths.
10. Add `userTypeOverrides` storage mechanism.
11. Add model type UI (badge + dropdown).
12. Add `hiddenKinds` filter to `getProvidersByKind()`.
13. Add `/v1/models/{kind}` endpoint.

---

## Artifacts

| Audit | Source Task | Full Report Location |
|-------|------------|---------------------|
| serviceKinds | t_1594051f | `audit-serviceKinds.md` (workspace) |
| Model Storage | t_acb22871 | `audit-model-storage-and-user-override.md` (workspace) |
| Endpoints | t_ce14cc8b | (findings in task metadata) |
| Regex | t_ed8f5a37 | (findings in task metadata) |
| **Compiled** | **t_f00719a3** | **This file** |

---

## Related Documents

- Plan: `docs/features/plan-provider-restructure.md`
- Provider analysis: `docs/providers-analysis.md`
- Feature docs: `docs/features/media-providers.md`
