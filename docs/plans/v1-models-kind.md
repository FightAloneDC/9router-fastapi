# Plan: GET /v1/models/{kind}

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/models/[kind]/route.js` + `src/app/api/v1/models/info/route.js`  
**Estimated effort:** Very Low — path-param alias for existing query-param filter + small info endpoint.

---

## What This Does

Two things:

1. **`GET /v1/models/{kind}`** — Returns models filtered by service kind using
   a URL path parameter (e.g., `/v1/models/tts`) instead of query parameter
   (e.g., `/v1/models?kind=tts`).

2. **`GET /v1/models/info?id={alias}/{modelId}`** — Returns detailed metadata
   for a single model (endpoint URL, capabilities, dimensions, voices URL, etc.).

```
Client → GET /v1/models/tts
           ↓
       map slug → service kind(s): "tts" → ["tts"]
           ↓
       reuse existing list_models logic with kind filter
           ↓
       return { object: "list", data: [{ id: "openai/tts-1", ... }] }
```

---

## Background

The existing FastAPI `GET /v1/models` endpoint already has a `kind` query
parameter filter (added in commit `feat: add kind filter to GET /v1/models`).
This works:

```bash
GET /v1/models?kind=tts
GET /v1/models?kind=embedding
GET /v1/models?kind=image
```

The original also supports path-based filtering:

```bash
GET /v1/models/tts
GET /v1/models/embedding
GET /v1/models/image
GET /v1/models/web          # maps to both webSearch + webFetch
GET /v1/models/image-to-text
GET /v1/models/stt
```

The path-based version is used by CLI tools and external clients that prefer
clean URLs over query parameters.

**Problem:** The existing FastAPI `GET /v1/models/{model_path:path}` handler
catches ALL path-based model requests and returns a generic model object:

```python
@router.get("/models/{model_path:path}")
async def get_model(model_path: str, ...):
    return {"id": model_path, "object": "model", "created": 0, "owned_by": "9router"}
```

This means `GET /v1/models/tts` returns `{"id": "tts", "object": "model"}`
instead of filtering models by kind. The catch-all handler intercepts the
kind-based route.

---

## Key Difference: Kind Slug Mapping

The original maps URL slugs to service kind arrays:

```javascript
const KIND_SLUG_MAP = {
  "image": ["image"],
  "tts": ["tts"],
  "stt": ["stt"],
  "embedding": ["embedding"],
  "image-to-text": ["imageToText"],
  "web": ["webSearch", "webFetch"],  // "web" covers both search and fetch
};
```

Note: `"web"` is a special slug that maps to BOTH `webSearch` and `webFetch`.
This is because the navigation sidebar groups them under "Web" providers.

---

## Phase 1 — Backend: Add Kind Slug Route

**File:** `backend/app/routers/v1_proxy.py`

The key challenge is route ordering. FastAPI matches routes in registration
order, and `{model_path:path}` is a catch-all. We need to register the
kind-based route BEFORE the catch-all.

### 1.1 Kind Slug Map

```python
KIND_SLUG_MAP = {
    "image": ["image"],
    "tts": ["tts"],
    "stt": ["stt"],
    "embedding": ["embedding"],
    "image-to-text": ["imageToText"],
    "web": ["webSearch", "webFetch"],
}
```

### 1.2 The Route Handler

```python
@router.get("/models/{kind}")
async def list_models_by_kind(
    kind: str,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """List models filtered by kind (path parameter version).
    
    Supported kinds: image, tts, stt, embedding, image-to-text, web.
    Falls back to the existing list_models handler with kind filter.
    """
    kind_slugs = KIND_SLUG_MAP.get(kind)
    
    if not kind_slugs:
        # Not a known kind slug — could be a model path
        # Return 404 with helpful message
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "message": f"Unknown model kind: {kind}. Supported: {', '.join(KIND_SLUG_MAP.keys())}",
                    "type": "invalid_request_error",
                }
            },
        )
    
    # Delegate to existing list_models with first kind as filter
    # For "web" slug (maps to webSearch + webFetch), we need to handle both
    if len(kind_slugs) == 1:
        return await list_models(kind=kind_slugs[0], db=db, api_key_info=api_key_info)
    else:
        # Multiple kinds (e.g., "web" → webSearch + webFetch)
        # Get results for each kind and merge
        all_models = []
        seen = set()
        for k in kind_slugs:
            result = await list_models(kind=k, db=db, api_key_info=api_key_info)
            if isinstance(result, dict) and "data" in result:
                for model in result["data"]:
                    if model["id"] not in seen:
                        all_models.append(model)
                        seen.add(model["id"])
        return {"object": "list", "data": all_models}
```

### 1.3 Route Registration Order

**Critical:** The `{kind}` route must be registered BEFORE `{model_path:path}`
so FastAPI matches it first. Since both use `@router.get("/models/...")`,
FastAPI will try to match in registration order.

However, FastAPI's path parameter matching doesn't distinguish between
`{kind}` (no path converter) and `{model_path:path}` (path converter).
The `{kind}` route without `:path` will match single-segment paths like
`/models/tts`, while `{model_path:path}` will match multi-segment paths
like `/models/openai/gpt-4o`.

**Solution:** Register the kind route explicitly before the catch-all:

```python
# Register kind-based route FIRST (matches single segment)
@router.get("/models/{kind}")
async def list_models_by_kind(kind: str, ...):
    ...

# Register catch-all route AFTER (matches multi-segment)
@router.get("/models/{model_path:path}")
async def get_model(model_path: str, ...):
    ...
```

FastAPI will try `{kind}` first for single-segment paths. If the kind is not
recognized, it returns 404 with the supported kinds list.

**Alternative approach:** If route ordering doesn't work cleanly, modify the
existing `get_model` handler to detect kind slugs:

```python
@router.get("/models/{model_path:path}")
async def get_model(model_path: str, ...):
    # Check if this is a kind slug
    if model_path in KIND_SLUG_MAP:
        return await list_models_by_kind(kind=model_path, db=db, api_key_info=api_key_info)
    
    # Otherwise, return generic model info
    return {"id": model_path, "object": "model", "created": 0, "owned_by": "9router"}
```

This is simpler and avoids route ordering issues.

---

## Phase 2 — Backend: Add `/v1/models/info` Route (Optional)

The original has `GET /v1/models/info?id={alias}/{modelId}` which returns
detailed metadata for a single model. This is a nice-to-have for CLI tools.

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.get("/models/info")
async def model_info(
    id: str = Query(..., description="Model ID in alias/model format (e.g. openai/gpt-4o)"),
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """Get detailed metadata for a single model."""
    from app.services.proxy import ALIAS_TO_ID, ID_TO_ALIAS, PROVIDER_CONFIGS
    from app.routers.providers.constants import PROVIDER_DEFAULTS, infer_model_type, MODEL_TYPE_OVERRIDES
    
    if "/" not in id:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "id must be in alias/model format (e.g. openai/gpt-4o)"}},
        )
    
    alias, model_id = id.split("/", 1)
    provider_id = ALIAS_TO_ID.get(alias, alias)
    provider_defaults = PROVIDER_DEFAULTS.get(provider_id, {})
    
    # Determine kind
    kind = "llm"
    if model_id in MODEL_TYPE_OVERRIDES:
        kind = MODEL_TYPE_OVERRIDES[model_id]
    else:
        kind = infer_model_type(model_id)
    
    # Build endpoint URL
    endpoint_map = {
        "llm": "/v1/chat/completions",
        "image": "/v1/images/generations",
        "tts": "/v1/audio/speech",
        "stt": "/v1/audio/transcriptions",
        "embedding": "/v1/embeddings",
        "imageToText": "/v1/chat/completions",
        "webSearch": "/v1/search",
        "webFetch": "/v1/web/fetch",
    }
    
    result = {
        "id": id,
        "name": model_id,
        "kind": kind,
        "owned_by": alias,
        "endpoint": endpoint_map.get(kind),
    }
    
    # Add voices URL for TTS providers
    tts_providers = {"elevenlabs", "edge-tts", "deepgram", "inworld", "local-device"}
    if kind == "tts" and provider_id in tts_providers:
        result["voicesUrl"] = f"/v1/audio/voices?provider={provider_id}"
    
    return result
```

---

## Phase 3 — Frontend: No Changes Required

Both endpoints are pure API endpoints. No UI changes needed.

---

## Phase 4 — Testing

### 4.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — TTS models (path param):**
```bash
curl -s "http://localhost:9000/v1/models/tts" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length), sample: .data[0]}'
```
Expected: Only TTS models returned. `count > 0`.

**Test 2 — Embedding models:**
```bash
curl -s "http://localhost:9000/v1/models/embedding" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```

**Test 3 — Image models:**
```bash
curl -s "http://localhost:9000/v1/models/image" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```

**Test 4 — STT models:**
```bash
curl -s "http://localhost:9000/v1/models/stt" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```

**Test 5 — Web models (maps to webSearch + webFetch):**
```bash
curl -s "http://localhost:9000/v1/models/web" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```

**Test 6 — Unknown kind (404):**
```bash
curl -s "http://localhost:9000/v1/models/nonexistent" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `404` with `"Unknown model kind: nonexistent"`.

**Test 7 — Query param still works (regression):**
```bash
curl -s "http://localhost:9000/v1/models?kind=tts" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```
Expected: Same results as path param version.

**Test 8 — Model info:**
```bash
curl -s "http://localhost:9000/v1/models/info?id=openai/tts-1" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `{id, name, kind: "tts", owned_by, endpoint, voicesUrl}`.

**Test 9 — Model info (missing id):**
```bash
curl -s "http://localhost:9000/v1/models/info" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `400` or `422` with missing parameter error.

### 4.2 Regression check

```bash
# Existing /v1/models still works
curl -s "http://localhost:9000/v1/models" \
  -H "Authorization: Bearer $TOKEN" | jq '.data | length'

# Chat completions still works
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 5 — Report

1. **`docs/porting-status.md`** — Move `GET /v1/models/{kind}` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 10 as ✅.
3. **`docs/plans/v1-models-kind.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Route ordering | Must ensure `{kind}` matches before `{model_path:path}`. Alternative: detect kind slugs inside the catch-all handler. |
| `"web"` slug maps to 2 kinds | `web` → `webSearch` + `webFetch`. Must merge results from both. |
| `/v1/models/info` is optional | The original has it but it's not critical. CLI tools use it for metadata. Phase 1 can skip it. |
| Model info metadata | `params`, `capabilities`, `dimensions`, `contextWindow` not available in FastAPI backend (stored in frontend constants only). Can be added later. |
| `searchConfig` metadata | Web search providers have `searchTypes`, `maxMaxResults` etc. Not available in FastAPI backend constants. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/routers/v1_proxy.py` | Add `GET /v1/models/{kind}` handler + `KIND_SLUG_MAP`, optional `GET /v1/models/info` |
| `docs/porting-status.md` | Move models/{kind} to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 10 done |
| `docs/plans/v1-models-kind.md` | Update status to Done |

No DB migrations. No frontend changes. No new files needed.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Kind slug mapping | Trivial | Dict lookup |
| Route handler | Trivial | Delegate to existing `list_models` |
| "web" multi-kind merge | Low | Loop over 2 kinds, deduplicate |
| Route ordering | Low | Register before catch-all, or detect in catch-all |
| `/v1/models/info` | Low | Simple metadata lookup from constants |

**Overall:** Very Low complexity — the simplest endpoint in the entire plan.
Essentially a URL alias for an existing feature. The `/v1/models/info` endpoint
is slightly more work but still straightforward.

**Recommended implementation:**
1. Add `KIND_SLUG_MAP` dict
2. Detect kind slugs in existing `get_model` handler (simplest approach)
3. Optionally add `/v1/models/info` endpoint
