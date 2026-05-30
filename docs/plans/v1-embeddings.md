# Plan: POST /v1/embeddings

**Status:** ✅ Done (2026-05-23) — Phase 1, 2, 4 implemented & live tested. Phase 5 reporting also complete.
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Frontend plan:** `docs/plans/v1-embeddings-frontend.md` (UI/UX fix)
**Original source:** `~/dev/9router/src/app/api/v1/embeddings/route.js` → `src/sse/handlers/embeddings.js`  
**Estimated effort:** Small — same pattern as existing chat proxy, pure JSON in/out, no streaming
**Last updated:** 2026-05-23

---

## What This Does

Adds an OpenAI-compatible embeddings endpoint to the FastAPI proxy. Clients send
a model + input text, 9Router resolves the provider, forwards to the upstream
embeddings API, and returns the embedding vector response.

```
Client → POST /v1/embeddings
           ↓
       resolve model alias → provider + connection
           ↓
       POST {provider_base_url}/embeddings
           ↓
       return { object: "list", data: [{embedding: [...]}], usage: {...} }
```

---

## Supported Providers

All providers with `serviceKinds` containing `"embedding"` in
`backend/app/routers/providers/constants.py`:

| Provider      | Base URL                                        | Auth         | Endpoint path    |
|---------------|-------------------------------------------------|--------------|------------------|
| openai        | https://api.openai.com/v1                       | Bearer       | /embeddings      |
| openrouter    | https://openrouter.ai/api/v1                    | Bearer       | /embeddings      |
| mistral       | https://api.mistral.ai/v1                       | Bearer       | /embeddings      |
| cohere        | https://api.cohere.ai/v1                        | Bearer       | /embeddings      |
| fireworks     | https://api.fireworks.ai/inference/v1           | Bearer       | /embeddings      |
| together      | https://api.together.xyz/v1                     | Bearer       | /embeddings      |
| nvidia        | https://integrate.api.nvidia.com/v1             | Bearer       | /embeddings      |
| siliconflow   | https://api.siliconflow.cn/v1                   | Bearer       | /embeddings      |
| nebius        | https://api.studio.nebius.ai/v1                 | Bearer       | /embeddings      |
| jina-ai       | https://api.jina.ai/v1                          | Bearer       | /embeddings      |
| github        | https://models.github.ai/inference             | Bearer       | /embeddings      |
| azure         | {azureEndpoint}/openai/deployments/{dep}/...    | api-key      | special URL      |
| gemini        | https://generativelanguage.googleapis.com/v1beta| query param  | special URL      |
| voyage-ai     | https://api.voyageai.com/v1                     | Bearer       | /embeddings      |

**Special cases:**
- **gemini**: URL is `{base}/models/{model}:embedContent?key={apiKey}` for single input,
  `batchEmbedContents` for array input. Response format differs — needs normalization.
- **azure**: URL is `{endpoint}/openai/deployments/{deployment}/embeddings?api-version={ver}`.
- **voyage-ai**: Not in `PROVIDER_CONFIGS` yet — needs to be added.

---

## Request / Response Format

**Request:**
```json
POST /v1/embeddings
Authorization: Bearer <jwt_or_api_key>
Content-Type: application/json

{
  "model": "openai/text-embedding-3-small",
  "input": "Hello world",
  "encoding_format": "float",
  "dimensions": 1536
}
```

`input` can be a string or array of strings. `encoding_format` and `dimensions`
are optional, passed through to upstream as-is.

**Response (OpenAI format):**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0023064255, -0.009327292, ...]
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {
    "prompt_tokens": 8,
    "total_tokens": 8
  }
}
```

---

## Phase 1 — Backend: Add `/v1/embeddings` Route ✅ DONE (2026-05-23)

**File:** `backend/app/routers/v1_proxy.py`

### Deviations from plan:
1. **Combo support added** — user requirement. Handler uses `get_combo_strategy()` +
   `_get_rotated_targets()` identically to `chat_completions`. Reason: same model
   can come from different API keys or providers with different model ID spellings.
2. **Gemini normalize helper NOT added** — skipped as recommended in plan.
   `_normalize_gemini_embeddings()` code is in the plan but not implemented.
   Gemini embeddings won't work until custom URL builder is added as follow-up.
3. **No unused imports** — plan had `from app.services.proxy import _resolve_base_url,
   PROVIDER_CONFIGS` but these aren't needed. `_build_embeddings_url()` only does
   string manipulation on `target.url`.
4. **Error handling pattern** — follows `chat_completions` pattern exactly
   (`httpx.HTTPStatusError` + `httpx.ConnectError` + generic `Exception`), not the
   simplified version in plan doc.

### 1.1 Add the route handler

Add after the existing `chat_completions` handler. The pattern is identical —
resolve targets, fallback loop, forward body, return response.

```python
@router.post("/embeddings")
async def embeddings(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """OpenAI-compatible embeddings proxy."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = body.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="Missing required field: model")

    if not body.get("input"):
        raise HTTPException(status_code=400, detail="Missing required field: input")

    targets = await resolve_model_to_targets(db, model, stream=False)
    if not targets:
        raise HTTPException(
            status_code=503,
            detail=f"No provider available for model: {model}",
        )

    last_error = None
    for target in targets:
        # Build upstream URL: replace /chat/completions with /embeddings
        upstream_url = _build_embeddings_url(target)
        forward_body = {**body, "model": target.model}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    upstream_url,
                    json=forward_body,
                    headers=target.headers,
                )
                if resp.status_code < 500:
                    # Normalize Gemini response if needed
                    data = resp.json()
                    if target.provider == "gemini":
                        data = _normalize_gemini_embeddings(data, target.model)
                    return JSONResponse(status_code=resp.status_code, content=data)
                last_error = {"status": resp.status_code, "detail": resp.text[:500]}
        except httpx.ConnectError as e:
            last_error = {"status": 503, "detail": str(e)}
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)}

    error_msg = last_error.get("detail", "All providers failed") if last_error else "No targets"
    error_status = last_error.get("status", 503) if last_error else 503
    return JSONResponse(status_code=error_status, content={"error": {"message": error_msg}})
```

### 1.2 Add `_build_embeddings_url()` helper

`resolve_model_to_targets()` builds a URL ending in `/chat/completions`.
For embeddings we need `/embeddings` instead. Add this helper in `v1_proxy.py`:

```python
def _build_embeddings_url(target: "ResolvedTarget") -> str:
    """Derive the embeddings endpoint URL from a resolved target.
    
    resolve_model_to_targets() always builds a /chat/completions URL.
    For embeddings we swap the path suffix.
    Special cases: gemini uses a different URL structure entirely.
    """
    from app.services.proxy import _resolve_base_url, PROVIDER_CONFIGS
    
    # Gemini: handled separately — URL built in normalize step
    # For all OpenAI-compat providers: swap /chat/completions → /embeddings
    url = target.url
    if url.endswith("/chat/completions"):
        return url[: -len("/chat/completions")] + "/embeddings"
    # Azure: swap deployments/{dep}/chat/completions → deployments/{dep}/embeddings
    if "/chat/completions" in url:
        return url.replace("/chat/completions", "/embeddings")
    # Fallback: append /embeddings to base
    return url.rstrip("/") + "/embeddings"
```

**Alternative (cleaner):** Add an `endpoint` parameter to
`resolve_model_to_targets()` in `services/proxy.py` so it builds the correct
URL from the start. This is the right long-term fix but touches the shared
service used by chat. Do this in a follow-up refactor, not in this task.

### 1.3 Add `_normalize_gemini_embeddings()` helper

Gemini returns a different response shape. Normalize to OpenAI format:

```python
def _normalize_gemini_embeddings(data: dict, model: str) -> dict:
    """Normalize Gemini embedContent/batchEmbedContents response to OpenAI format."""
    # Already normalized (shouldn't happen but guard)
    if data.get("object") == "list":
        return data

    items = []
    # batchEmbedContents response: {"embeddings": [{"values": [...]}]}
    if "embeddings" in data:
        for idx, emb in enumerate(data["embeddings"]):
            items.append({
                "object": "embedding",
                "index": idx,
                "embedding": emb.get("values", []),
            })
    # embedContent response: {"embedding": {"values": [...]}}
    elif "embedding" in data:
        items.append({
            "object": "embedding",
            "index": 0,
            "embedding": data["embedding"].get("values", []),
        })

    return {
        "object": "list",
        "data": items,
        "model": model,
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
```

**Note on Gemini URL:** `resolve_model_to_targets()` builds a Gemini chat URL
(`{base}/models/{model}:generateContent`). For embeddings, Gemini uses
`{base}/models/{model}:embedContent?key={apiKey}`. The `_build_embeddings_url()`
helper above won't handle this correctly.

Two options:
1. Detect `target.provider == "gemini"` in the route handler and build the URL
   manually using `_resolve_base_url()` + the API key from `target.headers`.
2. Accept that Gemini embeddings won't work in Phase 1 and add it as a follow-up.

**Recommendation:** Option 2 for Phase 1. Gemini embeddings are rarely used
compared to OpenAI/openrouter. Add a TODO comment and ship the rest.

---

## Phase 2 — Backend: Add `voyage-ai` to PROVIDER_CONFIGS ✅ DONE (2026-05-23)

**File:** `backend/app/services/proxy.py`

### Deviations from plan:
1. **`jina-ai` also added** — was missing from PROVIDER_CONFIGS despite being in
   PROVIDER_DEFAULTS (constants.py). Added alongside voyage-ai.
2. **No alias added to ALIAS_TO_ID** — as noted in plan, voyage-ai has no frontend
   alias. Users use `voyage-ai/model-name` format directly. Same for jina-ai.

`voyage-ai` is in `PROVIDER_DEFAULTS` (constants.py) with `serviceKinds: ["embedding"]`
but is missing from `PROVIDER_CONFIGS` in `proxy.py`. Without it, the proxy
can't build headers or resolve the base URL.

Add to `PROVIDER_CONFIGS`:

```python
"voyage-ai": {
    "base_url": "https://api.voyageai.com/v1",
    "format": "openai",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer ",
},
```

Also add to `ALIAS_TO_ID` if not present (check — voyage-ai has no alias in
the current frontend constants, so it may not need one).

---

## Phase 3 — Frontend: No Changes Required

The `/v1/embeddings` endpoint is a pure API endpoint. No UI changes needed.

The MediaProvidersPage already shows embedding providers (filtered by
`serviceKinds: ["embedding"]`). The ProviderDetailPage already handles adding
connections for embedding providers. Nothing to change.

**Optional future enhancement:** Add an "Embeddings" test button in
ProviderDetailPage for embedding providers, similar to the existing "Test
Connection" button. This is out of scope for this plan.

---

## Phase 4 — Testing

### 4.1 Manual curl tests

Run these against the running dev environment. Get a token first:

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Happy path (OpenAI, string input):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small", "input": "Hello world"}' \
  | jq '{object, model, usage, first_embedding_len: (.data[0].embedding | length)}'
```
Expected: `object: "list"`, embedding array with 1536 floats.

**Test 2 — Array input:**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small", "input": ["Hello", "World"]}' \
  | jq '{object, data_count: (.data | length)}'
```
Expected: `data_count: 2`.

**Test 3 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello"}' | jq .
```
Expected: `400` with `"Missing required field: model"`.

**Test 4 — Missing input (400):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small"}' | jq .
```
Expected: `400` with `"Missing required field: input"`.

**Test 5 — No auth token (401 if requireApiKey=true, or pass-through if false):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small", "input": "Hello"}' | jq .
```
Expected: depends on `requireApiKey` setting. If false → works. If true → 401.

**Test 6 — Unknown provider (503):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "nonexistent/model", "input": "Hello"}' | jq .
```
Expected: `503` with `"No provider available for model: nonexistent/model"`.

**Test 7 — openrouter embedding (if openrouter connection exists):**
```bash
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openrouter/text-embedding-3-small", "input": "Hello"}' | jq .
```

**Test 8 — Verify console log entry:**
```bash
curl -s http://localhost:9000/console/logs \
  -H "Authorization: Bearer $TOKEN" | jq '.[-1]'
```
Expected: last log entry shows `POST /v1/embeddings → 200`.

### 4.2 Verify in running app

1. Open http://localhost:5173 in browser.
2. Navigate to any embedding provider detail page (e.g. openai, jina-ai).
3. Confirm the page still loads correctly — no regressions from backend changes.
4. Check the Console Log page (http://localhost:5173/console-log) — the curl
   requests from 4.1 should appear in the log.

### 4.3 Regression check

Confirm existing chat completions still work after the changes:

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```
Expected: `"OK"` or similar short response.

---

## Phase 5 — Report

After implementation and testing, update the following:

1. **`docs/porting-status.md`** — Move `POST /v1/embeddings` from the
   "Not Yet Ported" table to the "Fully Ported" table.

2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 1 as done:
   change `POST /v1/embeddings` status to ✅.

3. **`docs/plans/v1-embeddings.md`** (this file) — Update status at top
   from `Not started` to `Done`, add completion date and any notes about
   deviations from this plan.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Gemini embeddings | Skipped in Phase 1. Needs custom URL builder (`embedContent` vs `generateContent`). Add as separate task. |
| voyage-ai alias | No frontend alias defined. Users must use `voyage-ai/model-name` format. |
| Azure embeddings | URL pattern differs (`/deployments/{dep}/embeddings`). `_build_embeddings_url()` handles the path swap but Azure URL is fully custom — test separately. |
| `encoding_format: "base64"` | Passed through as-is. Not all providers support it. No special handling needed. |
| `dimensions` param | Passed through as-is. Only supported by OpenAI `text-embedding-3-*` models. |
| Usage tracking | The existing usage router tracks chat completions. Embeddings usage is not tracked yet. Out of scope. |

---

## Files Changed Summary

| File | Change | Status |
|------|--------|--------|
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/embeddings` handler + `_build_embeddings_url()` | ✅ Done |
| `backend/app/services/proxy.py` | Add `voyage-ai` + `jina-ai` to `PROVIDER_CONFIGS` | ✅ Done |
| `docs/porting-status.md` | Move embeddings to ported table | ✅ Done (2026-05-23) |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 1 done | ✅ Done (2026-05-23) |
| `docs/plans/v1-embeddings.md` | Update status to Done | ✅ Done (2026-05-23) |

No DB migrations. No frontend changes. No new dependencies.

---

## Frontend Follow-up (same-day 2026-05-23)

Backend ship → frontend test playground butuh integrasi. Frontend work tracked separately di:

- `docs/plans/v1-embeddings-frontend.md` — Phase 1-5 UI/UX rewrite (Models card, real API call, curl snippet, latency, dimensions input) ✅ Done
- `docs/plans/fix-media-provider-detail-filter.md` — 3 follow-up bug fixes (models filter per kind, test endpoint routing, clipboard insecure-context fallback) ✅ Done

Backend endpoint `POST /v1/embeddings` verified live via:
1. curl smoke test (Test 1-8 in Phase 4 above)
2. Frontend Test Playground on `/media-providers/embedding/nvidia` — real call returned 200 OK with 1024-dim vector from `nvidia/nvidia/nv-embed-v1`
