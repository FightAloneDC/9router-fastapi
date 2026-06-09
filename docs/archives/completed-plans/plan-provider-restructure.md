# Plan: Provider Restructuring by Service Kind

## 1. Overview

Restructure the provider system so that providers are categorized by their
supported service kinds (LLM, Embedding, TTS, STT, Web Search, Images, etc.).

- `/providers` — only providers that support Chat/LLM
- `/media-providers/embedding` — providers with embedding support
- `/media-providers/tts` — providers with TTS support
- `/media-providers/stt` — providers with STT support
- `/media-providers/web` — providers with web search/fetch support
- `/media-providers/images` — providers with image generation support

Providers that support multiple kinds appear in multiple menus.

---

## 2. Current State Analysis

### 2.1 Backend (FastAPI)

- `PROVIDER_DEFAULTS` in `constants.py` — flat dict, NO `serviceKinds` field
- Models stored as flat string array: `data["models"] = ["gpt-4o", "gpt-4o-mini"]`
- NO model type field (llm, embedding, tts, etc.)
- NO service kind filtering in any API endpoint
- `/providers` returns ALL providers regardless of kind
- `_normalize_model()` returns `{id, name}` but only `id` is persisted

### 2.2 Frontend

- `providers.js` — already has `serviceKinds` per provider (client-side only)
- `getProvidersByKind(kind)` — client-side filtering function
- `MediaProvidersPage.jsx` — tab-based UI, filters client-side
- `MEDIA_PROVIDER_KINDS` constant defines kind metadata
- Frontend fetches ALL connections, filters locally

### 2.3 Original Node.js (reference)

- `serviceKinds` defined per provider in `providers.js`
- `providerModels.js` has static model definitions with `type` field
- `inferKindFromUnknownModelId()` — regex-based auto-detection
- `/v1/models` endpoint filters by kind
- Two-level classification: provider-level (serviceKinds) + model-level (type)

---

## 3. Service Kinds Definition

### 3.1 Available Kinds

Source: `providers.js` line 178-188 (`MEDIA_PROVIDER_KINDS`)

| Kind        | Label           | UI Tab    | API Endpoint                     |
|-------------|-----------------|-----------|----------------------------------|
| llm         | Chat/LLM        | Providers | POST /v1/chat/completions        |
| embedding   | Embedding       | Embedding | POST /v1/embeddings              |
| tts         | Text To Speech  | TTS       | POST /v1/audio/speech            |
| stt         | Speech To Text  | STT       | POST /v1/audio/transcriptions    |
| webSearch   | Web Search      | Web       | POST /v1/search                  |
| webFetch    | Web Fetch       | Web       | POST /v1/web/fetch               |
| image       | Text to Image   | Images    | POST /v1/images/generations      |
| imageToText | Image to Text   | (future)  | POST /v1/images/understanding    |
| video       | Video           | (future)  | POST /v1/video/generations       |
| music       | Music           | (future)  | POST /v1/audio/music             |

### 3.2 UI Tab Grouping

- **Providers page** (`/providers`): shows only providers with `"llm"` in serviceKinds
- **Media Providers page** (`/media-providers/*`): 5 tabs
  - Embedding tab → providers with `"embedding"`
  - TTS tab → providers with `"tts"`
  - STT tab → providers with `"stt"`
  - Web tab → providers with `"webSearch"` or `"webFetch"`
  - Images tab → providers with `"image"`

---

## 4. Provider → Service Kinds Mapping

Source of truth: ported from original Node.js `providers.js` `serviceKinds` field.
Providers WITHOUT explicit serviceKinds default to `["llm"]`.
Providers that are commented out in source are marked `[DISABLED]`.

### 4.1 LLM-Only Providers (default, no explicit serviceKinds needed)

These providers have NO explicit `serviceKinds` in source and default to `["llm"]`:

```
# FREE_PROVIDERS
kiro                          (deprecated)
gemini-cli                    (deprecated)
opencode                      (noAuth, passthroughModels)

# FREE_TIER_PROVIDERS
ollama
vertex

# OAUTH_PROVIDERS
claude                        (deprecated)
antigravity                   (deprecated)
cursor
kilocode
cline

# APIKEY_PROVIDERS
glm
glm-cn
alicode
alicode-intl
xiaomi-mimo
xiaomi-tokenplan
volcengine-ark
opencode-go
deepseek
commandcode
cerebras
siliconflow
chutes
ollama-local
vertex-partner

# WEB_COOKIE_PROVIDERS
grok-web
perplexity-web
```

NOTE: Some LLM-only providers have explicit `serviceKinds: ["llm"]`:
- `vercel-ai-gateway` — explicit `["llm"]`
- `blackbox` — explicit `["llm"]`
- `byteplus` — explicit `["llm"]`

### 4.2 Multi-Kind Providers (explicit serviceKinds required)

Verified from source `providers.js` — each line shows the EXACT serviceKinds array:

```
openai:           ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"]
openrouter:       ["llm", "embedding", "tts", "imageToText"]
gemini:           ["llm", "embedding", "image", "imageToText", "webSearch", "tts", "stt"]
nvidia:           ["llm", "tts", "embedding"]
groq:             ["llm", "imageToText", "stt"]
mistral:          ["llm", "imageToText", "embedding"]
together:         ["llm", "embedding"]
fireworks:        ["llm", "embedding"]
nebius:           ["llm", "embedding"]
hyperbolic:       ["llm", "tts"]
anthropic:        ["llm", "imageToText"]
codex:            ["llm", "image"]              (deprecated)
github:           ["llm", "embedding"]           (deprecated)
kimi:             ["llm", "webSearch"]
xai:              ["llm", "imageToText", "webSearch"]
perplexity:       ["llm", "webSearch"]
minimax:          ["llm", "image", "imageToText", "webSearch", "tts"]
minimax-cn:       ["llm", "tts"]
cloudflare-ai:    ["llm", "image"]
huggingface:      ["image", "imageToText", "tts", "stt"]   ← NOTE: NO "llm"
```

### 4.3 Media-Only Providers (NO llm kind)

```
# Web Search/Fetch
tavily:              ["webSearch", "webFetch"]
brave-search:        ["webSearch"]
serper:              ["webSearch"]
exa:                 ["webSearch", "webFetch"]
searxng:             ["webSearch"]
google-pse:          ["webSearch"]
linkup:              ["webSearch"]
searchapi:           ["webSearch"]
youcom:              ["webSearch"]
firecrawl:           ["webFetch"]
jina-reader:         ["webFetch"]

# Image Generation
fal-ai:              ["image"]
stability-ai:        ["image"]
black-forest-labs:   ["image"]
recraft:             ["image"]
topaz:               ["image"]
runwayml:            ["image", "video"]
nanobanana:          ["image"]
sdwebui:             ["image"]
comfyui:             ["image"]

# TTS Only
elevenlabs:          ["tts"]
cartesia:            ["tts"]         (hidden)
playht:              ["tts"]         (hidden)
local-device:        ["tts"]         (noAuth)
google-tts:          ["tts"]         (noAuth)
edge-tts:            ["tts"]         (noAuth)
coqui:               ["tts"]         (hidden, noAuth)
tortoise:            ["tts"]         (hidden, noAuth)
inworld:             ["tts"]
aws-polly:           ["tts"]

# STT Only
assemblyai:          ["stt"]

# Multi-media (non-LLM)
deepgram:            ["stt", "imageToText", "tts"]
voyage-ai:           ["embedding"]
jina-ai:             ["embedding"]
```

### 4.4 Disabled/Commented-Out Providers

These appear in source but are commented out. Their serviceKinds (from comments)
are preserved here for reference:

```
qwen:              ["llm", "tts"]               (FREE_PROVIDERS, disabled)
iflow:             LLM-only                     (FREE_PROVIDERS, disabled)
kimi-coding:       LLM-only                     (OAUTH_PROVIDERS, disabled)
```

### 4.5 Providers in Plan That Do NOT Exist in Source

These were listed in the old plan but are NOT in the original `providers.js`:

```
amazon-bedrock     — NOT in source
volcengine         — NOT in source (volcengine-ark exists)
kilo-gateway       — NOT in source
chutes-legacy      — NOT in source
huggingchat        — NOT in source
crawl4ai           — NOT in source
replicate          — NOT in source
nanobanana-img     — NOT in source (nanobanana exists)
assemblyai-stt     — NOT in source (assemblyai exists)
you-com            — NOT in source (youcom exists)
bfl                — NOT in source (black-forest-labs exists)
```

Disabled (commented out) free-tier providers from source:
```
agentrouter, aimlapi, novita, modal, reka, nlpcloud, bazaarlink,
completions, enally, freetheai, llm7, lepton, kluster, ai21,
inference-net, predibase, bytez, morph, longcat, puter, uncloseai,
scaleway, deepinfra, sambanova, nscale, baseten, publicai,
nous-research, glhf
```

---

## 5. Model Type System

### 5.1 Model Storage Format Change

**Current** (flat string array):
```json
{
  "models": ["gpt-4o", "text-embedding-3-small", "tts-1"]
}
```

**New** (array of objects with type):
```json
{
  "models": [
    {"id": "gpt-4o", "type": "llm"},
    {"id": "text-embedding-3-small", "type": "embedding"},
    {"id": "tts-1", "type": "tts"}
  ]
}
```

### 5.2 Backward Compatibility

When reading existing data, if a model entry is a plain string, treat as
`{"id": "<string>", "type": "llm"}`. Migration happens lazily on read.

### 5.3 Model Type Auto-Detection (from route.js)

Source: `route.js` lines 39-60 — `MODEL_TYPE_TO_KIND` + `inferKindFromUnknownModelId()`

The original uses TWO mechanisms:

**A) MODEL_TYPE_TO_KIND** (line 39-45) — maps per-model `type` field to service kind:

```javascript
const MODEL_TYPE_TO_KIND = {
  image: "image",
  tts: "tts",
  embedding: "embedding",
  stt: "stt",
  imageToText: "imageToText",
};
// Models without `type` default to "llm"
```

**B) inferKindFromUnknownModelId()** (line 54-60) — regex fallback for dynamic
models (compatible providers, custom models, aliases) where no static type exists:

```javascript
function inferKindFromUnknownModelId(modelId) {
  const lower = String(modelId).toLowerCase();
  if (/embed/.test(lower)) return "embedding";
  if (/tts|speech|audio|voice/.test(lower)) return "tts";
  if (/image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion/.test(lower)) return "image";
  return LLM_KIND;  // "llm"
}
```

**Python port of regex inference:**

```python
def infer_model_type(model_id: str) -> str:
    """Infer model type from model ID using regex heuristics.
    Faithful port of Node.js inferKindFromUnknownModelId().
    Only matches embedding, tts, image — everything else returns "llm".
    There is NO stt regex in the original source.
    """
    mid = model_id.lower()

    # Embedding models
    if re.search(r"embed", mid):
        return "embedding"

    # TTS models
    if re.search(r"tts|speech|audio|voice", mid):
        return "tts"

    # Image models
    if re.search(r"image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion", mid):
        return "image"

    # Default: LLM
    return "llm"
```

**NOTE:** The original regex does NOT detect STT (whisper/transcri/stt/asr).
STT models must have their type set explicitly via the per-model `type` field.

### 5.4 Per-Model Type Overrides (from providerModels.js)

There is NO `MODEL_TYPE_OVERRIDES` dict in the original source. Instead, each
model in `PROVIDER_MODELS` can have an explicit `type` field. Models without
`type` default to `"llm"` (see `modelKind()` in route.js line 47-50).

Below is the COMPLETE list of all models with explicit `type` fields, verified
from `providerModels.js`:

**type: "embedding"**
```
# openai
text-embedding-3-large
text-embedding-3-small
text-embedding-ada-002

# gemini
gemini-embedding-2-preview
gemini-embedding-001
text-embedding-005
text-embedding-004

# github (gh)
text-embedding-3-small
text-embedding-3-large

# openrouter
openai/text-embedding-3-large
openai/text-embedding-3-small
openai/text-embedding-ada-002
qwen/qwen3-embedding-8b
perplexity/pplx-embed-v1-4b
perplexity/pplx-embed-v1-0.6b
nvidia/llama-nemotron-embed-vl-1b-v2:free

# mistral
mistral-embed

# together
BAAI/bge-large-en-v1.5
togethercomputer/m2-bert-80M-8k-retrieval

# fireworks
nomic-ai/nomic-embed-text-v1.5

# nvidia
nvidia/nv-embedqa-e5-v5

# nebius
Qwen/Qwen3-Embedding-8B

# voyage-ai
voyage-3-large, voyage-3.5, voyage-3.5-lite
voyage-code-3, voyage-finance-2, voyage-law-2
voyage-multilingual-2
```

**type: "tts"**
```
# openai
tts-1, tts-1-hd, gpt-4o-mini-tts

# openrouter
openai/gpt-4o-mini-tts, openai/tts-1-hd, openai/tts-1
```

**type: "stt"**
```
# openai
whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe

# groq
whisper-large-v3, whisper-large-v3-turbo, distil-whisper-large-v3-en

# gemini (multimodal generateContent)
gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash

# nvidia
nvidia/parakeet-ctc-1.1b-asr

# huggingface
openai/whisper-large-v3, openai/whisper-small

# deepgram
nova-3, nova-2, whisper-large

# assemblyai
universal-3-pro, universal-2
```

**type: "image"**
```
# codex (cx)
gpt-5.5-image, gpt-5.4-image, gpt-5.3-image, gpt-5.2-image

# openai
gpt-image-1, dall-e-3, dall-e-2

# gemini
gemini-3.1-flash-image-preview, gemini-3-pro-image-preview, gemini-2.5-flash-image

# openrouter
openai/dall-e-3, openai/gpt-image-1
google/imagen-3.0-generate-002
black-forest-labs/FLUX.1-schnell

# minimax
minimax-image-01

# cloudflare-ai
@cf/black-forest-labs/flux-2-klein-9b
@cf/black-forest-labs/flux-2-klein-4b
@cf/black-forest-labs/flux-2-dev
@cf/black-forest-labs/flux-1-schnell
@cf/leonardo/lucid-origin
@cf/leonardo/phoenix-1.0
@cf/bytedance/stable-diffusion-xl-lightning
@cf/lykon/dreamshaper-8-lcm
@cf/runwayml/stable-diffusion-v1-5-img2img
@cf/runwayml/stable-diffusion-v1-5-inpainting
@cf/stabilityai/stable-diffusion-xl-base-1.0

# nanobanana
nanobanana-flash, nanobanana-pro

# sdwebui
stable-diffusion-v1-5, sdxl-base-1.0

# comfyui
flux-dev, sdxl

# huggingface
black-forest-labs/FLUX.1-schnell
stabilityai/stable-diffusion-xl-base-1.0

# fal-ai
fal-ai/flux/schnell, fal-ai/flux/dev
fal-ai/flux-pro/v1.1, fal-ai/flux-pro/v1.1-ultra
fal-ai/recraft-v3, fal-ai/ideogram/v2
fal-ai/stable-diffusion-v35-large

# stability-ai
stable-image-ultra, stable-image-core
sd3.5-large, sd3.5-large-turbo, sd3.5-medium

# black-forest-labs
flux-pro-1.1, flux-pro-1.1-ultra, flux-pro, flux-dev
flux-kontext-pro (edit), flux-kontext-max (edit)

# recraft
recraftv3, recraftv2

# runwayml
gen4_image, gen4_image_turbo
```

**type: "video"**
```
# runwayml
gen4_turbo, gen3a_turbo
```

### 5.5 User Override

User can change model type via per-provider settings:
- `PATCH /providers/{conn_id}/models/{model_id}/type`
- Body: `{"type": "embedding"}`
- Stored in `data["modelTypes"]` map: `{"model-id": "embedding"}`

Priority order:
1. User override (`data["modelTypes"]`)
2. Per-model `type` field from providerModels.js (or fetched from provider API)
3. Regex inference (`infer_model_type()`) — only for unknown/dynamic models
4. Default: `"llm"`

### 5.6 Helper Functions (from route.js)

```javascript
// modelKind() — resolves model type to service kind
function modelKind(model) {
  if (!model?.type) return "llm";
  return MODEL_TYPE_TO_KIND[model.type] || "llm";
}

// providerMatchesKinds() — checks if provider supports any of requested kinds
function providerMatchesKinds(providerId, kindFilter) {
  const provider = AI_PROVIDERS[providerId];
  const kinds = Array.isArray(provider?.serviceKinds) && provider.serviceKinds.length > 0
    ? provider.serviceKinds
    : ["llm"];
  return kindFilter.some((k) => kinds.includes(k));
}
```

---

## 6. Backend Changes

### 6.1 Phase 1: Add serviceKinds to Provider Constants

**File**: `backend/app/routers/providers/constants.py`

Add `serviceKinds` field to every provider in `PROVIDER_DEFAULTS`:

```python
PROVIDER_DEFAULTS = {
    "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "validationType": "openai",
        "serviceKinds": ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"],
    },
    "anthropic": {
        "baseUrl": "https://api.anthropic.com/v1",
        "validationType": "anthropic",
        "serviceKinds": ["llm", "imageToText"],
    },
    # ... all providers (see section 4 for complete mapping)
}
```

Providers without explicit `serviceKinds` default to `["llm"]`.

### 6.2 Phase 2: Model Type in Storage

**File**: `backend/app/routers/providers/models.py`

Change `_normalize_model()` to include type:

```python
def _normalize_model(raw: dict) -> dict:
    model_id = raw.get("id") or raw.get("name") or ""
    name = raw.get("name") or model_id
    # Use explicit type if provided, otherwise infer
    model_type = raw.get("type") or infer_model_type(model_id)
    return {"id": model_id, "name": name, "type": model_type}
```

Change storage to persist full objects:

```python
# Before: data["models"] = [m["id"] for m in models]
# After:
data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]
```

### 6.3 Phase 3: Model Type User Override

**File**: `backend/app/routers/providers/models.py`

New endpoint:

```
PATCH /providers/{conn_id}/models/type
Body: {"model_id": "text-embedding-3-small", "type": "embedding"}
```

Stores in `data["modelTypes"]`:
```json
{
  "modelTypes": {
    "text-embedding-3-small": "embedding",
    "gpt-4o": "llm"
  }
}
```

### 6.4 Phase 4: Filtered Model Endpoints

**File**: `backend/app/routers/providers/models.py`

New endpoint for fetching models filtered by kind:

```
GET /providers/{conn_id}/models?kind=embedding
```

Returns only models whose resolved type matches the requested kind.

### 6.5 Phase 5: Provider List Filtering

**File**: `backend/app/routers/providers/connections.py`

Modify `/providers` endpoint to accept optional `kind` filter:

```
GET /providers?kind=llm           → only LLM providers
GET /providers?kind=embedding     → only embedding providers
GET /providers                    → all providers (backward compat)
```

Filtering logic:
```python
def provider_matches_kind(provider_id: str, kind: str) -> bool:
    defaults = PROVIDER_DEFAULTS.get(provider_id, {})
    kinds = defaults.get("serviceKinds", ["llm"])
    return kind in kinds
```

### 6.6 Phase 6: Media Providers API

**File**: `backend/app/routers/media_providers.py` (new)

```
GET /media-providers
Response: {
  "embedding": [{"id": "openai", "name": "OpenAI", ...}, ...],
  "tts": [...],
  "stt": [...],
  "webSearch": [...],
  "webFetch": [...],
  "image": [...],
}

GET /media-providers/{kind}
Response: [{"id": "openai", "name": "OpenAI", ...}, ...]
```

### 6.7 Phase 7: /v1/models Kind Filtering

**File**: `backend/app/routers/v1_proxy.py`

Modify `/v1/models` to filter by kind:

```
GET /v1/models                    → LLM models only (default)
GET /v1/models?kind=embedding     → embedding models only
GET /v1/models?kind=tts           → TTS models only
```

Uses resolved model type (user override > static > regex > default llm).

---

## 7. Frontend Changes

### 7.1 Phase 1: Move serviceKinds to API-Driven

**Files**: `frontend/src/constants/providers.js`, `frontend/src/api/providers.js`

- Remove `serviceKinds` from frontend constants (or keep as fallback)
- Fetch serviceKinds from backend `/providers` or `/media-providers` API
- `getProvidersByKind()` calls backend API instead of client-side filter

### 7.2 Phase 2: Providers Page Filter

**File**: `frontend/src/pages/ProvidersPage.jsx`

- Default fetch: `GET /providers?kind=llm`
- Only show providers with LLM support
- Model list: only show models with type "llm" (or no type = default llm)

### 7.3 Phase 3: Media Providers Page

**File**: `frontend/src/pages/MediaProvidersPage.jsx`

- Fetch from `GET /media-providers/{kind}` instead of client-side filter
- Tabs: Embedding | TTS | STT | Web | Images
- Each tab shows providers for that kind

### 7.4 Phase 4: Model Type Display

**Files**: Provider detail pages, model list components

- Show model type badge next to each model name
- Allow user to change model type via dropdown
- Type change calls `PATCH /providers/{conn_id}/models/type`

### 7.5 Phase 5: Navigation Update

**File**: `frontend/src/constants/navigation.js`

- `/providers` — LLM providers only
- `/media-providers` — sub-items for each kind tab

---

## 8. Migration & Backward Compatibility

### 8.1 Model Storage Migration

Existing connections have `data["models"] = ["id1", "id2"]`.

On read, detect format:
```python
def normalize_models_list(models):
    if not models:
        return []
    result = []
    for m in models:
        if isinstance(m, str):
            result.append({"id": m, "type": "llm"})
        elif isinstance(m, dict):
            result.append(m)
    return result
```

No DB migration needed — lazy upgrade on first read.

### 8.2 API Backward Compatibility

- `GET /providers` without `kind` param → returns all providers (current behavior)
- `GET /providers/{id}/models` → returns models with type field added
- Existing frontend continues to work during migration

---

## 9. Implementation Tasks

### Phase 1: Backend Foundation (serviceKinds + Model Type)
1. Add `serviceKinds` to all providers in `PROVIDER_DEFAULTS`
2. Add `infer_model_type()` function (faithful port of regex from route.js)
3. Change `_normalize_model()` to include type
4. Change model storage to persist `{id, type}` objects
5. Add backward-compat reader for old string-format models

### Phase 2: Backend API (Filtering + Endpoints)
6. Add `kind` query param to `GET /providers`
7. Create `GET /media-providers` endpoint
8. Create `GET /media-providers/{kind}` endpoint
9. Add `PATCH /providers/{conn_id}/models/type` endpoint
10. Add `kind` query param to `GET /v1/models`

### Phase 3: Frontend (Providers Page)
11. Update ProvidersPage to fetch `?kind=llm`
12. Update model list to show type badges
13. Add model type change UI (dropdown per model)

### Phase 4: Frontend (Media Providers Page)
14. Update MediaProvidersPage to fetch from API
15. Update MediaProviderDetailPage with type-aware model list
16. Update navigation.js

### Phase 5: Testing & QA
17. Test all provider kinds render correctly
18. Test model type auto-detection accuracy
19. Test user model type override persistence
20. Test backward compatibility with existing connections

---

## 10. Risks & Considerations

1. **Model type inference accuracy** — regex heuristics may misclassify edge
   cases. Mitigation: static overrides + user correction.

2. **Existing connections** — lazy migration means first read is slightly slower.
   Acceptable tradeoff vs forced DB migration.

3. **Frontend/backend sync** — during migration, frontend may have stale
   serviceKinds. Mitigation: backend is source of truth, frontend falls back.

4. **Provider additions** — new providers need `serviceKinds` added to
   `PROVIDER_DEFAULTS`. Without it, they default to `["llm"]`.

5. **Media-only providers in /providers** — providers like `brave-search`,
   `fal-ai` must NOT appear in `/providers` (no `"llm"` kind). Ensure
   filtering is correct.

6. **huggingface special case** — huggingface has `["image", "imageToText",
   "tts", "stt"]` but NO "llm". It will NOT appear on the Providers page.

7. **TTS sub-config models** — providers like openai, gemini, nvidia, etc.
   have TTS/embedding models defined in `ttsConfig.models` and
   `embeddingConfig.models` on the provider object, not in PROVIDER_MODELS.
   These must also be included when building models lists for those kinds.
   See route.js lines 349-369.

8. **Web search/fetch virtual models** — web search providers expose
   `{alias}/search` and `{alias}/fetch` virtual model IDs with explicit
   `kind` field. See route.js lines 371-387.

---

## 11. Implementation Status (FastAPI Backend Audit)

> Status against the FastAPI backend codebase as of 2026-05-21.
> The plan describes the IDEAL architecture; this section documents
> how much of it was actually implemented vs. what remains.

### Overall: Core Foundation Done, API Surface Missing

The **backend foundation** (serviceKinds data, model type inference, lazy
normalization) was implemented but **no filtering API endpoints** were built.
The frontend still filters entirely client-side using its own `serviceKinds`
constants.

---

### Phase 1: Backend Foundation — ✅ MOSTLY DONE

| Task | Code Location | Status |
|------|--------------|--------|
| `serviceKinds` in PROVIDER_DEFAULTS | `constants.py:10-107` | **DONE** — 40+ providers have explicit `serviceKinds`; others default to `["llm"]` via read logic |
| `infer_model_type()` regex port | `constants.py:217-242` | **DONE** — faithful port of original `inferKindFromUnknownModelId()` |
| `_normalize_model()` includes type | `helpers.py:177-184` | **DONE** — returns `{id, name, type}` using overrides + regex inference |
| `normalize_models_list()` backward compat | `constants.py:245-260` | **DONE** — handles both string and object formats on read |
| `MODEL_TYPE_OVERRIDES` static map | `constants.py:149-214` | **DONE** — 65+ model-to-type mappings |
| Change storage to persist `{id, type}` objects | `models.py:450,480,505,546` | **PARTIAL** — stores flat strings `[m["id"] for m in models]` but enriches to `{id, type}` on read via `normalize_models_list()` in `helpers.py:63` |

**Deviation**: Models are still stored as flat string arrays in DB, but
all read paths transparently convert them to typed objects. This is the
lazy migration pattern described in §8.1, just without the final write-path
change.

---

### Phase 2: Backend API — ❌ NOT STARTED

| Task | Expected | Status |
|------|----------|--------|
| `kind` query param on `GET /providers` | §6.5 | **NOT DONE** — `list_providers()` accepts no kind param |
| `GET /media-providers` endpoint | §6.6 | **NOT DONE** — no `media_providers.py` router exists |
| `GET /media-providers/{kind}` endpoint | §6.6 | **NOT DONE** — same |
| `PATCH /providers/{id}/models/type` | §6.3 | **NOT DONE** — no model type override endpoint |
| `kind` query param on `GET /v1/models` | §6.7 | **NOT DONE** — `list_models()` has no kind filter |

**Deviation**: Zero API endpoints for kind filtering were built. The backend
has all the data structures needed (serviceKinds on providers, model types
on normalization), but no way to query or filter by them through the API.

---

### Phase 3: Frontend Providers Page — ❌ NOT STARTED

| Task | Status |
|------|--------|
| ProvidersPage fetch `?kind=llm` | **NOT DONE** — fetches all providers |
| Model list shows type badges | **NOT DONE** — no type-aware display |
| Model type change UI (dropdown) | **NOT DONE** — no type override UI |

---

### Phase 4: Frontend Media Providers Page — ⚠️ PARTIALLY DONE

| Task | Status |
|------|--------|
| MediaProvidersPage fetch from API | **NOT DONE** — uses client-side `getProvidersByKind()` filter |
| MediaProviderDetailPage type-aware models | **NOT DONE** — no model type awareness |
| Navigation update (`/media-providers` routes) | **DONE** — sidebar has sub-tabs for each kind |

**What works**: `getProvidersByKind(kind)`, `MEDIA_PROVIDER_KINDS`, tab-based
UI with 5 tabs (Embedding, TTS, STT, Web, Images), navigation sidebar.

**Deviation**: The frontend implements filtering entirely client-side using
hardcoded `serviceKinds` in the provider constants (same as the original
Node.js architecture). The plan intended for the backend to be source of
truth, but the frontend still fetches ALL connections and filters locally.

---

### Phase 5: Testing & QA — ❌ NOT STARTED

| Check | Status |
|-------|--------|
| Provider kinds render correctly | ⚠️ Client-side only, untested with backend |
| Model type auto-detection accuracy | ❌ Not tested |
| User model type override persistence | ❌ Not implemented |
| Backward compatibility | ⚠️ Lazy read migration works but untested |

---

### Key Deviations Summary

1. **Foundation built, APIs missing** — serviceKinds data and model type
   infrastructure exist in the backend, but no endpoints expose them for
   filtering. The `PROVIDER_DEFAULTS` in `constants.py` has `serviceKinds`
   on 40+ providers (including ALL multi-kind and media-only providers).

2. **Frontend still does all filtering** — `getProvidersByKind()` filters
   client-side, identical to the original Node.js approach. The plan's
   core goal of backend-as-source-of-truth was never reached.

3. **No model type endpoints** — `infer_model_type()`, `_normalize_model()`,
   and `normalize_models_list()` all work correctly in the backend, but
   there's no UI or API for users to override model types.

4. **Storage format mismatch** — Models are stored as flat strings but
   enriched to typed objects on every read. Works correctly but the write
   path stores redundant `id` fields without type info.

### Recommendation

To complete this restructure:
1. **API endpoints first** — Add `kind` param to `GET /providers`, create
   GET /media-providers endpoint, add model type override endpoint
2. **Fix storage format** — Change `data["models"] = [m["id"] for m in models]`
   to `data["models"] = [{"id": m["id"], "type": m["type"]} for m in models]`
3. **Migrate frontend** — Switch from client-side `getProvidersByKind()` to
   API-driven kind filtering
4. **Add model type UI** — Type badges and user override dropdown
