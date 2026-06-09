# Backend-Driven Providers Plan

**Goal:** Eliminate hardcoded provider-specific logic from the frontend. All provider metadata, OAuth flow types, and UI config should be served from the backend via a new `/providers/catalog` endpoint.

**Status:** Draft
**Created:** 2026-06-08

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Current State](#2-current-state)
3. [Gap Analysis](#3-gap-analysis)
4. [Architecture](#4-architecture)
5. [Implementation Phases](#5-implementation-phases)
6. [Migration Strategy](#6-migration-strategy)
7. [Files Changed](#7-files-changed)

---

## 1. Problem Statement

The frontend (`constants/providers.js`, 218 lines) duplicates ~80 provider definitions that already exist in backend `providers/<name>/config.py`. This creates two failure modes:

- **Drift:** Adding a new provider requires changes in both backend AND frontend
- **Hardcoded logic:** `OAuthModal.jsx` contains hardcoded provider lists (`DEVICE_CODE_PROVIDERS`, `PAT_IMPORT_PROVIDERS`) and provider-specific conditionals (`if provider === 'codex'`) that should be derived from backend handler metadata

**PS Rule violated:** "All provider-specific logic MUST live in `backend/app/providers/<provider>/`."

---

## 2. Current State

### Backend (already exists, 97 provider folders)

```
backend/app/providers/
├── __init__.py              # PROVIDER_X constants (97 providers)
├── base.py                  # BaseProviderConfig + BaseMetadata + BaseProviderHandler
├── provider.py              # Provider class — unified accessor
├── oauth_base.py            # BaseOAuthHandler → AuthCodeHandler, DeviceCodeHandler, ImportTokenHandler
├── cerebras/
│   ├── config.py            # CerebrasConfig + CerebrasMetadata
│   └── models.py            # fetch_models(), parse_response()
└── ... (97 providers, all with config.py + Metadata)
```

Each provider config.py already has:
- `PROVIDER_NAME`, `PROVIDER_ID`, `ALIAS`, `BASE_URL`
- `SERVICE_KINDS`, `VALIDATION_TYPE`, `FORMAT`
- `AUTH_HEADER`, `AUTH_PREFIX`, `AUTH_QUERY_PARAM`
- Metadata: `name`, `color`, `textIcon`

OAuth handlers already have:
- `PROVIDER_ID`, `FLOW_TYPE`, `CONFIG` (auto-discovered via `pkgutil`)

### Frontend (hardcoded, 218 lines)

```js
// constants/providers.js
FREE_PROVIDERS = { kiro: {...}, qwen: {...}, ... }       // 5 providers
FREE_TIER_PROVIDERS = { openrouter: {...}, nvidia: {...}, ... } // 7 providers
OAUTH_PROVIDERS = { claude: {...}, codex: {...}, ... }   // 7 providers
APIKEY_PROVIDERS = { glm: {...}, deepseek: {...}, ... }  // 47 providers
WEB_COOKIE_PROVIDERS = { "grok-web": {...}, ... }        // 2 providers
```

Each entry has 8-15 fields. Total: ~68 providers × ~12 fields = ~816 field values hardcoded.

### What's NOT in backend yet (frontend-only fields)

| Field | Used By | Description |
|-------|---------|-------------|
| `icon` | ProvidersPage, ProviderDetailPage | Lucide icon component name (string) |
| `website` | ProviderDetailPage "Visit site" link | Provider homepage URL |
| `notice` | ProvidersPage, AddKeyModal | Signup/upgrade/tooltip text + URLs |
| `deprecated` | ProvidersPage badge, filtering | Whether to show deprecation warning |
| `deprecationNotice` | ProviderDetailPage warning banner | Deprecation reason text |
| `hidden` | Filtering (don't show in main list) | Hidden from default listing |
| `noAuth` | AddKeyModal (skip credential input) | Provider doesn't need auth |
| `passthroughModels` | Model list behavior | Use upstream models directly |
| `hasProviderSpecificData` | AddKeyModal (show extra fields) | Needs Azure endpoint, region, etc. |
| `regions` | AddKeyModal region dropdown | Available region options |
| `defaultRegion` | AddKeyModal default | Default region selection |
| `thinkingConfig` | ChatPage thinking mode controls | Extended thinking / effort config |
| `mediaPriority` | MediaProvidersPage sorting | Display order in media list |
| `authType` | AddKeyModal credential label | "cookie" vs default |
| `authHint` | AddKeyModal placeholder | Credential input hint text |

---

## 3. Gap Analysis

### What backend CAN already serve (zero config changes)

| Frontend Value | Backend Source | Notes |
|---|---|---|
| `id` | `config.PROVIDER_ID` | Direct |
| `alias` | `config.ALIAS` | Direct |
| `name` | `metadata.name` | Direct |
| `color` | `metadata.color` | Direct |
| `textIcon` | `metadata.textIcon` | Direct |
| `serviceKinds` | `config.SERVICE_KINDS` | Direct |
| `flowType` | `handler.FLOW_TYPE` | Via OAuth service |
| `authType` | Derive from handler + config | `oauth` / `apikey` / `cookie` / `free` |

### What needs new fields in backend config

| Frontend Value | New Backend Field | Type | Default |
|---|---|---|---|
| `icon` | `BaseMetadata.icon` | `str` | `"Box"` |
| `website` | `BaseMetadata.website` | `str` | `""` |
| `notice` | `BaseMetadata.notice` | `dict \| None` | `None` |
| `deprecated` | `BaseProviderConfig.DEPRECATED` | `bool` | `False` |
| `deprecationNotice` | `BaseProviderConfig.DEPRECATION_NOTICE` | `str` | `""` |
| `hidden` | `BaseProviderConfig.HIDDEN` | `bool` | `False` |
| `noAuth` | `BaseProviderConfig.NO_AUTH` | `bool` | `False` |
| `passthroughModels` | `BaseProviderConfig.PASSTHROUGH_MODELS` | `bool` | `False` |
| `hasProviderSpecificData` | Derive from handler/config | `bool` | `False` |
| `regions` | `BaseProviderConfig.REGIONS` | `list[dict] \| None` | `None` |
| `defaultRegion` | `BaseProviderConfig.DEFAULT_REGION` | `str` | `""` |
| `thinkingConfig` | `BaseProviderConfig.THINKING_CONFIG` | `dict \| None` | `None` |
| `mediaPriority` | `BaseProviderConfig.MEDIA_PRIORITY` | `int` | `100` |
| `authHint` | `BaseMetadata.authHint` | `str` | `""` |
| `modelsFetcher` | `BaseProviderConfig.MODELS_FETCHER` | `dict \| None` | `None` |

---

## 4. Architecture

### New endpoint: `GET /providers/catalog`

```
GET /api/providers/catalog
Authorization: Bearer <token>

Response:
{
  "providers": {
    "cerebras": {
      "id": "cerebras",
      "alias": "cb",
      "name": "Cerebras",
      "color": "#FF6B00",
      "textIcon": "CB",
      "icon": "Cpu",
      "serviceKinds": ["llm"],
      "website": "https://cloud.cerebras.ai",
      "notice": { "apiKeyUrl": "https://cloud.cerebras.ai/" },
      "flowType": null,
      "authType": "apikey",
      "deprecated": false,
      "hidden": false,
      "noAuth": false,
      "passthroughModels": false,
      "hasProviderSpecificData": false,
      "regions": null,
      "defaultRegion": "",
      "thinkingConfig": null,
      "mediaPriority": 100,
      "modelsFetcher": null
    },
    "qoder": {
      "id": "qoder",
      "alias": "qd",
      "name": "Qoder",
      "color": "#8B5CF6",
      "textIcon": "QD",
      "icon": "Zap",
      "serviceKinds": ["llm"],
      "website": "https://qoder.com",
      "notice": { "signupUrl": "https://qoder.com" },
      "flowType": "device_code",
      "authType": "oauth",
      "deprecated": false,
      "hidden": false,
      "noAuth": false,
      "supportsPAT": true,
      ...
    },
    ...
  },
  "categories": {
    "free": ["kiro", "qwen", "gemini-cli", "iflow", "opencode"],
    "freeTier": ["openrouter", "nvidia", "ollama", ...],
    "oauth": ["claude", "antigravity", "codex", ...],
    "apiKey": ["glm", "deepseek", "groq", ...],
    "webCookie": ["grok-web", "perplexity-web"]
  },
  "mediaKinds": [
    { "id": "embedding", "label": "Embedding", "icon": "Binary", "endpoint": {...} },
    ...
  ],
  "compatiblePrefixes": {
    "openai": "openai-compatible-",
    "anthropic": "anthropic-compatible-",
    "customEmbedding": "custom-embedding-"
  }
}
```

### Data flow

```
┌──────────────────────────────────────────────────────────────────┐
│  Backend                                                         │
│                                                                  │
│  providers/<name>/config.py ──┐                                  │
│    Config + Metadata          │                                  │
│                               ▼                                  │
│  services/catalog.py ──▶ iter_modules(AVAILABLE_PROVIDERS)       │
│    collect_catalog()         load Config + Metadata              │
│                              resolve OAuth handler flow_type     │
│                              return merged dict                  │
│                               │                                  │
│                               ▼                                  │
│  routers/providers/          GET /providers/catalog              │
│                               │                                  │
└───────────────────────────────┼──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Frontend                                                        │
│                                                                  │
│  api/providers.js ──▶ fetchCatalog()                             │
│    cache in Zustand store                                        │
│                               │                                  │
│       ┌───────────────────────┼──────────────────────┐           │
│       ▼                       ▼                      ▼           │
│  ProvidersPage         ProviderDetailPage      OAuthModal        │
│    useCatalog()          useCatalog()           useCatalog()     │
│    PROVIDERS[p.id]       PROVIDERS[p.id]        flowType,        │
│    (from store)          (from store)           supportsPAT,     │
│                                                 authType         │
│                                                                  │
│  constants/providers.js ──▶ REMOVED (replaced by catalog)        │
│    Only keep: MEDIA_PROVIDER_KINDS (static), helpers             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Phases

### Phase 1: Extend Backend Config Schema

**Objective:** Add missing UI metadata fields to `BaseProviderConfig` and `BaseMetadata`.

**Files:**
- `backend/app/providers/base.py` — add fields to `BaseProviderConfig` and `BaseMetadata`
- `backend/app/providers/<all 82 providers>/config.py` — add new field values to each Metadata + Config

**Changes to `base.py`:**

```python
class BaseProviderConfig(BaseModel):
    # ... existing fields ...

    # ── UI Metadata (served via /providers/catalog) ──────────────
    DEPRECATED: bool = False
    DEPRECATION_NOTICE: str = ""
    HIDDEN: bool = False
    NO_AUTH: bool = False
    PASSTHROUGH_MODELS: bool = False
    REGIONS: list[dict] | None = None
    DEFAULT_REGION: str = ""
    THINKING_CONFIG: dict | None = None
    MEDIA_PRIORITY: int = 100
    MODELS_FETCHER: dict | None = None
    SUPPORTS_PAT: bool = False  # for OAuth providers that also accept PAT


class BaseMetadata(BaseModel):
    # ... existing fields (name, color, textIcon) ...
    icon: str = "Box"
    website: str = ""
    notice: dict | None = None
    authHint: str = ""
```

**Verify:** All existing provider configs still load correctly (no breaking changes since all new fields have defaults).

---

### Phase 2: Backend Catalog Endpoint

**Objective:** Create `GET /providers/catalog` that serves merged config+metadata for all providers.

**New file:** `backend/app/services/catalog.py`

```python
def collect_catalog() -> dict:
    """Collect provider catalog from all AVAILABLE_PROVIDERS."""
    providers = {}
    for provider_id in AVAILABLE_PROVIDERS:
        try:
            p = Provider(provider_id)
            c = p.config()
            m = p.metadata()
            oauth_handler = _try_get_oauth_handler(provider_id)

            providers[provider_id] = {
                "id": c.PROVIDER_ID,
                "alias": c.ALIAS,
                "name": m.name,
                "color": m.color,
                "textIcon": m.textIcon,
                "icon": m.icon,
                "website": m.website,
                "notice": m.notice,
                "authHint": m.authHint,
                "serviceKinds": c.SERVICE_KINDS or ["llm"],
                "flowType": oauth_handler.flow_type if oauth_handler else None,
                "authType": _derive_auth_type(c, oauth_handler),
                "deprecated": c.DEPRECATED,
                "deprecationNotice": c.DEPRECATION_NOTICE,
                "hidden": c.HIDDEN,
                "noAuth": c.NO_AUTH,
                "passthroughModels": c.PASSTHROUGH_MODELS,
                "hasProviderSpecificData": bool(c.REGIONS) or c.PROVIDER_ID in ("azure", "amazon-bedrock", "cloudflare-ai", "xiaomi-tokenplan"),
                "regions": c.REGIONS,
                "defaultRegion": c.DEFAULT_REGION,
                "thinkingConfig": c.THINKING_CONFIG,
                "mediaPriority": c.MEDIA_PRIORITY,
                "modelsFetcher": c.MODELS_FETCHER,
                "supportsPAT": c.SUPPORTS_PAT,
            }
        except Exception:
            logger.warning("Failed to load catalog for %s", provider_id, exc_info=True)
            continue
    return providers
```

**Modify:** `backend/app/routers/providers/connections.py` (or `_router.py`)

```python
@router.get("/providers/catalog")
async def providers_catalog():
    """Return full provider catalog for frontend."""
    from app.services.catalog import collect_catalog
    return {"providers": collect_catalog()}
```

**Verify:** `curl http://localhost:9000/providers/catalog -H "Authorization: Bearer $TOKEN" | jq '.providers.cerebras'`

---

### Phase 3: Migrate Non-Provider Metadata to Catalog

**Objective:** Serve `categories`, `mediaKinds`, `compatiblePrefixes`, `authMethods` from backend.

Extend `collect_catalog()` to also return:

```python
{
  "providers": { ... },
  "categories": {
    "free": ["kiro", "qwen", ...],
    "freeTier": ["openrouter", "nvidia", ...],
    "oauth": ["claude", "codex", ...],
    "apiKey": ["glm", "deepseek", ...],
    "webCookie": ["grok-web", "perplexity-web"],
  },
  "mediaKinds": [
    {"id": "embedding", "label": "Embedding", "icon": "Binary", "endpoint": {"method": "POST", "path": "/v1/embeddings"}},
    ...
  ],
  "compatiblePrefixes": {
    "openai": "openai-compatible-",
    "anthropic": "anthropic-compatible-",
    "customEmbedding": "custom-embedding-"
  },
  "authMethods": {
    "oauth": {"id": "oauth", "name": "OAuth", "icon": "Lock"},
    "apikey": {"id": "apikey", "name": "API Key", "icon": "Key"},
    "cookie": {"id": "cookie", "name": "Browser Cookie", "icon": "Cookie"}
  }
}
```

**Categories** are derived from backend constants — no new fields needed:
- `free` = providers with `NO_AUTH=True` or special OAuth free tier
- `freeTier` = providers with free tier (new field `FREE_TIER: bool = False` or hardcoded list in catalog service)
- `oauth` = providers with discovered OAuth handler
- `apiKey` = everything else
- `webCookie` = providers with `AUTH_TYPE="cookie"` (new field or derive from config)

**Verify:** Full catalog response matches what `providers.js` currently exports.

---

### Phase 4: Frontend Zustand Store + API

**Objective:** Frontend fetches catalog on init, stores in Zustand, replaces all imports from `constants/providers.js`.

**New file:** `frontend/src/stores/catalogStore.js`

```js
import { create } from 'zustand'
import client from '../api/client'

const useCatalogStore = create((set, get) => ({
  providers: {},
  categories: {},
  mediaKinds: [],
  compatiblePrefixes: {},
  authMethods: {},
  loaded: false,
  loading: false,

  fetchCatalog: async () => {
    if (get().loaded || get().loading) return
    set({ loading: true })
    try {
      const res = await client.get('/providers/catalog')
      const data = res.data
      set({
        providers: data.providers || {},
        categories: data.categories || {},
        mediaKinds: data.mediaKinds || [],
        compatiblePrefixes: data.compatiblePrefixes || {},
        authMethods: data.authMethods || {},
        loaded: true,
        loading: false,
      })
    } catch (err) {
      console.error('[catalog] Failed to fetch provider catalog:', err)
      set({ loading: false })
    }
  },

  // Backward-compatible accessors
  getProvider: (id) => get().providers[id],
  getProvidersByKind: (kind) => {
    return Object.values(get().providers)
      .filter(p => {
        const kinds = p.serviceKinds ?? ['llm']
        if (!kinds.includes(kind)) return false
        if (p.hidden) return false
        return true
      })
      .sort((a, b) => (a.mediaPriority ?? 100) - (b.mediaPriority ?? 100))
  },
  getProviderByAlias: (alias) => {
    return Object.values(get().providers).find(
      p => p.alias === alias || p.id === alias
    ) || null
  },
}))

export default useCatalogStore
```

**Modify:** `frontend/src/App.jsx` — fetch catalog on mount

```jsx
import useCatalogStore from './stores/catalogStore'

function App() {
  const fetchCatalog = useCatalogStore(s => s.fetchCatalog)
  useEffect(() => { fetchCatalog() }, [])
  // ...
}
```

**Verify:** Open app, check `useCatalogStore.getState().loaded === true` in browser console.

---

### Phase 5: Replace constants/providers.js Usage

**Objective:** Remove all imports of `constants/providers.js` from pages and components. Replace with `useCatalogStore`.

**Files to modify (priority order):**

| File | Current Import | Replace With |
|------|---------------|--------------|
| `ProvidersPage.jsx` | `AI_PROVIDERS`, `OAUTH_PROVIDERS`, `FREE_PROVIDERS`, etc. | `useCatalogStore` |
| `ProviderDetailPage.jsx` | `AI_PROVIDERS`, `OAUTH_PROVIDERS`, `FREE_PROVIDERS` | `useCatalogStore` |
| `OAuthModal.jsx` | `DEVICE_CODE_PROVIDERS`, `PAT_IMPORT_PROVIDERS` | `useCatalogStore.providers[id].flowType` |
| `MediaProvidersPage.jsx` | `getProvidersByKind`, `MEDIA_PROVIDER_KINDS` | `useCatalogStore` |
| `MediaProviderDetailPage.jsx` | `AI_PROVIDERS` | `useCatalogStore` |
| `ChatPage.jsx` | `getProvidersByKind`, `PROVIDERS` | `useCatalogStore` |
| `QuotaTrackerPage.jsx` | `USAGE_SUPPORTED_PROVIDERS` | Derive from catalog |
| `UsagePage.jsx` | `USAGE_SUPPORTED_PROVIDERS` | Derive from catalog |
| `ModelAvailabilityBadge.jsx` | Provider lookups | `useCatalogStore` |
| `ProviderTopology.jsx` | Provider lookups | `useCatalogStore` |

**Verify:** No remaining imports from `constants/providers.js` in any page/component.

---

### Phase 6: Refactor OAuthModal — Dynamic Flow Dispatch

**Objective:** Remove all hardcoded provider checks from OAuthModal.

**Before (hardcoded):**
```js
const DEVICE_CODE_PROVIDERS = ['github', 'qwen', 'kiro', 'kimi-coding', 'kilocode', 'codebuddy', 'qoder']
const PAT_IMPORT_PROVIDERS = ['qoder']

if (PAT_IMPORT_PROVIDERS.includes(provider)) { ... }
if (DEVICE_CODE_PROVIDERS.includes(provider)) { ... }
if (provider === 'codex') { redirectUri = 'http://localhost:1455/auth/callback' }
if (provider === 'kiro' && idcConfig?.startUrl) { ... }
const extraData = provider === 'kiro' ? { ... } : provider === 'qoder' ? { ... } : null
```

**After (dynamic):**
```js
const catalog = useCatalogStore(s => s.providers[provider])

const flowType = catalog?.flowType           // "device_code" | "authorization_code_pkce" | "import_token" | null
const supportsPAT = catalog?.supportsPAT     // true for qoder
const authType = catalog?.authType           // "oauth" | "apikey" | "cookie"

// Flow dispatch by flowType, not by provider name
if (supportsPAT && effectiveMethod === null) {
  setStep('choose')
  return
}

if (flowType === 'device_code') {
  setIsDeviceCode(true)
  // ... device code flow (generic, no provider checks)
}

// Auth code flow (generic)
redirectUri = `http://localhost:${appPort}/callback`
```

**Provider-specific extraData** is handled by backend — the `/device-code` and `/poll` endpoints already return/accept `_prefixed` keys. Frontend just passes through `data.extra` without inspecting it.

**Codex proxy** stays as special case but uses `catalog.flowType === 'authorization_code_pkce'` + `catalog.requiresProxy === true` instead of `provider === 'codex'`.

**Verify:** Test OAuth flow for: codex (PKCE+proxy), kiro (device code), qoder (device code + PAT choice), cursor (import).

---

### Phase 7: Refactor ProviderDetailPage — Dynamic Modal Selection

**Objective:** Remove hardcoded `providerId === 'kiro' ? <KiroAuthModal />` chain.

**Before:**
```jsx
{providerId === 'kiro' ? <KiroAuthModal />
 : providerId === 'cursor' ? <CursorAuthModal />
 : providerId === 'gitlab' ? <GitLabAuthModal />
 : <OAuthModal />}
```

**After:** All providers use the same `<OAuthModal />` — it already handles all flow types dynamically (from Phase 6). The provider-specific modals (`KiroAuthModal`, `CursorAuthModal`, `GitLabAuthModal`) are either:

1. **Merged into OAuthModal** — OAuthModal already handles device_code, import_token, auth_code flows. Kiro's social login and Cursor's auto-import are just extra buttons within those flows.
2. **Or kept as variants** — loaded dynamically via `catalog.uiComponent` field.

**Option 1 is preferred** for maximum PS compliance (one modal, data-driven).

**Also remove:**
```js
// Line 42 — hardcoded qoder check
if (conn?.provider === 'qoder' || providerId === 'qoder') return true
// Replace with: catalog.supportsPAT || conn?.auth_type === 'oauth'

// Line 280-283 — hardcoded identity checks
const isOllamaLocal = providerId === "ollama-local"
const isAzure = providerId === "azure"
const isCloudflareAi = providerId === "cloudflare-ai"
// Replace with: catalog.hasProviderSpecificData, catalog.noAuth, etc.
```

**Verify:** All 80+ providers render correct modal and auth UI without any provider-name checks.

---

### Phase 8: Cleanup

1. **Delete or gut `constants/providers.js`**
   - Keep: `THINKING_CONFIG` (static constant), `MEDIA_PROVIDER_KINDS` (will come from catalog), helper functions (rewired to store)
   - Delete: all `*_PROVIDERS` objects (now in catalog)
   - Keep: `OPENAI_COMPATIBLE_PREFIX` etc. (will come from catalog `compatiblePrefixes`)

2. **Delete provider-specific modals** (if merged into OAuthModal)
   - `KiroAuthModal.js` (components or pages)
   - `CursorAuthModal.jsx`
   - `GitLabAuthModal.jsx`

3. **Add `USAGE_SUPPORTED_PROVIDERS` to catalog** or derive from `serviceKinds` + connection data.

4. **Backend: populate new fields for all 82 providers**
   - Script or manual: add `icon`, `website`, `notice`, `deprecated` etc. to each provider's config.py
   - This is the biggest volume of changes but mechanically simple

**Verify:**
- `grep -r 'constants/providers' frontend/src/` → 0 matches
- `grep -r 'DEVICE_CODE_PROVIDERS\|PAT_IMPORT_PROVIDERS' frontend/src/` → 0 matches
- `grep -r 'provider === "' frontend/src/pages/` → 0 matches

---

## 6. Migration Strategy

### Incremental rollout (no big-bang)

```
Phase 1-3 (Backend)  ─── Can deploy independently, additive only
Phase 4   (Store)    ─── Additive, doesn't break existing code
Phase 5   (Replace)  ─── Migrate one page at a time
Phase 6-7 (Refactor) ─── Depends on Phase 5 complete
Phase 8   (Cleanup)  ─── Final, removes dead code
```

During migration, both systems coexist:
- `constants/providers.js` still exists as fallback
- `useCatalogStore` fetches from backend
- Pages that import from `providers.js` continue to work
- Migrate one page per commit

### Rollback safety

- Catalog endpoint is read-only, additive
- If catalog fails to load, frontend falls back to `constants/providers.js`
- No database migration needed (all config is code-level, not DB)

---

## 7. Files Changed

### New files
| File | Phase | Description |
|------|-------|-------------|
| `backend/app/services/catalog.py` | 2 | Catalog collector service |
| `backend/app/routers/providers/catalog.py` | 2 | Catalog endpoint |
| `frontend/src/stores/catalogStore.js` | 4 | Zustand store for catalog |
| `docs/plans/ps-frontend-compliance/` | — | This plan |

### Modified files (backend)
| File | Phase | Description |
|------|-------|-------------|
| `backend/app/providers/base.py` | 1 | Add UI metadata fields |
| `backend/app/providers/<82>/config.py` | 1 | Add new field values |
| `backend/app/routers/providers/_router.py` | 2 | Include catalog router |

### Modified files (frontend)
| File | Phase | Description |
|------|-------|-------------|
| `frontend/src/App.jsx` | 4 | Fetch catalog on mount |
| `frontend/src/pages/ProvidersPage.jsx` | 5 | Use catalog store |
| `frontend/src/pages/ProviderDetailPage.jsx` | 5, 7 | Use catalog store + dynamic modals |
| `frontend/src/components/OAuthModal.jsx` | 6 | Dynamic flow dispatch |
| `frontend/src/pages/MediaProvidersPage.jsx` | 5 | Use catalog store |
| `frontend/src/pages/MediaProviderDetailPage.jsx` | 5 | Use catalog store |
| `frontend/src/pages/ChatPage.jsx` | 5 | Use catalog store |
| `frontend/src/pages/QuotaTrackerPage.jsx` | 5 | Use catalog store |
| `frontend/src/pages/UsagePage.jsx` | 5 | Use catalog store |
| `frontend/src/components/ModelAvailabilityBadge.jsx` | 5 | Use catalog store |
| `frontend/src/components/ProviderTopology.jsx` | 5 | Use catalog store |

### Deleted files (Phase 8)
| File | Reason |
|------|--------|
| `frontend/src/constants/providers.js` | Replaced by catalog endpoint + store |
| Provider-specific OAuth modals | Merged into unified OAuthModal |

---

## Appendix: Compliance Checklist

After all phases complete, verify:

```bash
# Backend: zero provider-specific conditionals in routers
grep -n 'provider ==' backend/app/routers/oauth.py          # → 0
grep -n 'import httpx' backend/app/routers/oauth.py         # → 0
grep -n 'if provider' backend/app/routers/oauth.py          # → 0

# Frontend: zero hardcoded provider lists
grep -r 'DEVICE_CODE_PROVIDERS\|PAT_IMPORT_PROVIDERS' frontend/src/  # → 0
grep -r "=== 'qoder'\|=== 'kiro'\|=== 'codex'\|=== 'cursor'" frontend/src/pages/  # → 0
grep -r 'constants/providers' frontend/src/                           # → 0

# Frontend: all provider data from catalog
grep -r 'useCatalogStore' frontend/src/pages/ | wc -l     # → matches page count
```
