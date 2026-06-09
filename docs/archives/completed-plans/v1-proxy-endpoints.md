# Plan: v1 Proxy Endpoints

**Status:** Not started  
**Priority:** High  
**Goal:** Port all missing `/v1/*` proxy endpoints from the original Next.js 9router
so the FastAPI port functions as a full proxy router, not just an LLM forwarder.

---

## Background

The original 9router exposes a full OpenAI-compatible API surface. The FastAPI
port currently only has:

- `POST /v1/chat/completions` ✅
- `GET /v1/models` ✅

Everything else is missing. This plan covers all remaining v1 endpoints.

---

## Architecture: How the Existing Proxy Works

Before implementing anything, understand the existing pattern in
`backend/app/routers/v1_proxy.py` and `backend/app/services/proxy.py`.

### Provider resolution (`services/proxy.py`)

```
model string (e.g. "an/claude-sonnet-4")
  → _resolve_provider_alias("an") → "anthropic"
  → DB lookup: ProviderConnection where provider="anthropic" AND is_active=True
  → _resolve_base_url() → base URL (from connection data.baseUrl or PROVIDER_CONFIGS)
  → _build_upstream_url() → full upstream URL
  → _build_headers() → auth headers (Bearer / x-api-key / etc.)
  → ResolvedTarget(url, headers, provider, model, connection_id)
```

### Fallback loop pattern (`v1_proxy.py`)

```python
targets = await resolve_model_to_targets(db, model, stream=False)
for target in targets:
    try:
        response = await httpx_client.post(target.url, headers=target.headers, json=body)
        if response.status_code < 500:
            return response  # success or client error — don't retry
        # 5xx → try next target
    except httpx.RequestError:
        continue  # network error → try next target
raise HTTPException(502, "All upstream targets failed")
```

### Key services to reuse

- `services/proxy.py → resolve_model_to_targets()` — already handles alias
  resolution, DB lookup, combo expansion, and URL/header building.
- `services/proxy.py → PROVIDER_CONFIGS` — has base URLs and auth headers for
  all providers. New endpoints need to extend `_build_upstream_url()` with
  per-endpoint path logic.
- `routers/auth.py → get_current_user()` — JWT auth dependency, already used
  by all existing endpoints.

### What needs to change in `services/proxy.py`

`_build_upstream_url()` currently always appends `/chat/completions`. Each new
endpoint type needs its own path. The cleanest approach is to add an `endpoint`
parameter:

```python
def _build_upstream_url(provider, base_url, stream=False, data=None, model="", endpoint="chat") -> str:
    # endpoint: "chat" | "embeddings" | "tts" | "stt" | "images" | "search" | "fetch"
```

Or alternatively, each new router builds its own URL directly using
`_resolve_base_url()` + `_build_headers()` without going through
`_build_upstream_url()`. This is simpler and avoids touching the existing
chat proxy.

**Recommended:** Each new endpoint builds its own upstream URL. Reuse only
`_resolve_base_url()`, `_build_headers()`, and the DB lookup pattern.
Do NOT modify `_build_upstream_url()` — it's used by the working chat proxy.

---

## Endpoint Breakdown

### 1. `POST /v1/embeddings` ✅ Done (2026-05-23)

See dedicated plan: `docs/plans/v1-embeddings.md` (Phase 1, 2, 4, 5 all complete).
Frontend follow-up: `docs/plans/fix-media-provider-detail-filter.md` (3 UI/UX fixes shipped same day).

**Original:** `src/sse/handlers/embeddings.js`  
**Pattern:** Identical to chat — resolve `model` field, credential fallback loop,
forward JSON body to upstream `/v1/embeddings`.

**Request body (OpenAI-compatible):**
```json
{ "model": "openai/text-embedding-3-small", "input": "Hello world" }
```

**Upstream URL:** `{base_url}/embeddings`

**Providers to support:** openai, openrouter, mistral, cohere, fireworks,
together, nvidia, siliconflow, jina-ai, huggingface, azure, vertex, nebius,
gemini (all providers with `serviceKinds` containing `"embedding"`).

**Implementation steps:**
1. Add `POST /v1/embeddings` route to `routers/v1_proxy.py`.
2. Parse `model` from body. Validate `input` field present.
3. Resolve provider via `resolve_model_to_targets(db, model)`.
4. Build upstream URL: `{base_url}/embeddings`.
5. Forward body as-is (strip internal fields if any).
6. Return upstream response directly (no streaming needed).
7. Fallback loop: on 5xx try next target.

**Verify:** `curl -X POST http://localhost:9000/v1/embeddings -H "Authorization: Bearer $TOKEN" -d '{"model":"openai/text-embedding-3-small","input":"hello"}'`

---

### 2. `POST /v1/audio/speech` (TTS) 🟡 Iterasi 1 Done (2026-05-23)

Group A adapters (openai, siliconflow, hyperbolic) wired and structurally validated.
Group B (gemini, elevenlabs, minimax, openrouter, deepgram, nvidia, huggingface,
inworld, cartesia, playht) pending Iterasi 2-3. See dedicated plan:
`docs/plans/v1-audio-speech.md` for completion report and iteration tracking.

**Original:** `src/sse/handlers/tts.js`  
**Pattern:** Resolve `model` (format: `{alias}/{voice_id}`), credential fallback
loop, forward to upstream TTS endpoint, return binary audio response.

**Request body (OpenAI-compatible):**
```json
{ "model": "openai/alloy", "input": "Hello world", "voice": "alloy" }
```

**Upstream URL:** `{base_url}/audio/speech`

**Key difference from chat:** Response is binary audio (mp3/wav/opus), not JSON.
Must stream binary response back to client with correct `Content-Type`.

**Providers to support:** openai, gemini, nvidia, siliconflow, minimax,
minimax-cn, huggingface, azure, hyperbolic (all with `serviceKinds` containing
`"tts"`).

**Implementation steps:**
1. Add `POST /v1/audio/speech` route to `routers/v1_proxy.py`.
2. Parse `model` from body. Validate `input` field present.
3. Resolve provider via `resolve_model_to_targets(db, model)`.
4. Build upstream URL: `{base_url}/audio/speech`.
5. Forward body as-is.
6. Return binary response with `Content-Type` from upstream (audio/mpeg, audio/wav, etc.).
   Use `Response(content=..., media_type=upstream_content_type)`.
7. Fallback loop on 5xx.

**Note:** `response_format` query param (`mp3` default, `wav`, `opus`, `aac`)
should be passed through to upstream as query param or in body depending on
provider.

**Verify:** `curl -X POST http://localhost:9000/v1/audio/speech -H "Authorization: Bearer $TOKEN" -d '{"model":"openai/alloy","input":"Hello"}' --output test.mp3`

---

### 3. `POST /v1/audio/transcriptions` (STT)

**Original:** `src/sse/handlers/stt.js`  
**Pattern:** Multipart form data (not JSON). Resolve `model` from form field,
credential fallback loop, forward multipart to upstream.

**Request:** `multipart/form-data` with fields:
- `model` — e.g. `"openai/whisper-1"` or `"groq/whisper-large-v3"`
- `file` — audio file (binary)
- `language` — optional ISO 639-1 code
- `prompt` — optional context string
- `response_format` — optional (`json`, `text`, `srt`, `vtt`)

**Upstream URL:** `{base_url}/audio/transcriptions`

**Key difference:** Request is multipart, not JSON. Use `httpx` multipart
forwarding. FastAPI receives via `UploadFile` + `Form` params.

**Providers to support:** openai, groq, assemblyai, huggingface, gemini,
azure (all with `serviceKinds` containing `"stt"`).

**Implementation steps:**
1. Add `POST /v1/audio/transcriptions` route to `routers/v1_proxy.py`.
2. Accept `file: UploadFile`, `model: str = Form(...)`, plus optional form fields.
3. Resolve provider from `model` field via `_resolve_provider_alias()` + DB lookup.
   (Cannot use `resolve_model_to_targets` directly since it expects JSON body —
   build a small helper or inline the lookup.)
4. Build upstream URL: `{base_url}/audio/transcriptions`.
5. Forward as multipart using `httpx` files parameter.
6. Return upstream JSON response.
7. Fallback loop on 5xx.

**Verify:** `curl -X POST http://localhost:9000/v1/audio/transcriptions -H "Authorization: Bearer $TOKEN" -F "model=openai/whisper-1" -F "file=@test.mp3"`

---

### 4. `GET /v1/audio/voices`

**Original:** `src/app/api/v1/audio/voices/route.js`  
**Pattern:** NOT a proxy — delegates to internal `/media-providers/tts/{provider}/voices`
endpoints. Returns OpenAI-style list with `model` field set to `{alias}/{voice_id}`.

**Request:** `GET /v1/audio/voices?provider={provider_id}[&lang={lang}]`

**Supported providers:** `elevenlabs`, `deepgram`, `inworld`, `edge-tts`, `local-device`

**Response:**
```json
{
  "object": "list",
  "data": [
    { "id": "alloy", "name": "Alloy", "lang": "en", "gender": "female", "model": "el/alloy" }
  ]
}
```

**Note:** This endpoint depends on the TTS voices sub-endpoints
(`/media-providers/tts/elevenlabs/voices`, etc.) which are also not yet ported.
Those are in the "Media Provider Voices" section of the gap analysis.

**Implementation steps:**
1. Add `GET /v1/audio/voices` route to `routers/v1_proxy.py`.
2. Read `provider` query param. Validate against supported list.
3. Call the internal media-providers voices endpoint (or implement inline).
4. Map response to OpenAI-style list with `model = "{alias}/{voice_id}"`.
5. Return `{"object": "list", "data": [...]}`.

**Dependency:** Requires `/media-providers/tts/{provider}/voices` to be
implemented first, OR implement voice fetching inline in this endpoint.
Inline is simpler for now — add a `VOICES_PROVIDERS` dict mapping provider
to their voices API URL + auth pattern.

**Verify:** `curl "http://localhost:9000/v1/audio/voices?provider=elevenlabs" -H "Authorization: Bearer $TOKEN"`

---

### 5. `POST /v1/images/generations`

**Original:** `src/sse/handlers/imageGeneration.js`  
**Pattern:** Resolve `model`, credential fallback loop, forward to upstream
image generation endpoint. Response is JSON with `data[].url` or `data[].b64_json`.

**Request body (OpenAI-compatible):**
```json
{ "model": "fal/flux-schnell", "prompt": "A cat", "n": 1, "size": "1024x1024" }
```

**Upstream URL:** `{base_url}/images/generations`

**Special cases:**
- `fal-ai`: URL is `https://fal.run/{model_id}` (different structure)
- `stability-ai`: URL is `https://api.stability.ai/v2beta/stable-image/generate/...`
- `cloudflare-ai`: URL includes account ID

**Providers to support:** openai, fal-ai, stability-ai, siliconflow, huggingface,
cloudflare-ai, nanobanana, minimax, codex (all with `serviceKinds` containing
`"image"`).

**Implementation steps:**
1. Add `POST /v1/images/generations` route to `routers/v1_proxy.py`.
2. Parse `model` and `prompt` from body. Validate both present.
3. Resolve provider via `resolve_model_to_targets(db, model)`.
4. Build upstream URL: `{base_url}/images/generations`.
   Handle special cases for fal-ai and stability-ai (add to `_build_upstream_url`
   or handle inline with a provider-specific URL builder).
5. Forward body as-is.
6. Return upstream JSON response.
7. Fallback loop on 5xx.

**Verify:** `curl -X POST http://localhost:9000/v1/images/generations -H "Authorization: Bearer $TOKEN" -d '{"model":"openai/dall-e-3","prompt":"A cat"}'`

---

### 6. `POST /v1/search`

**Original:** `src/sse/handlers/search.js`  
**Pattern:** Provider IS the model (no separate model field). Resolve provider
from `body.provider || body.model`, credential fallback loop, forward to
provider-specific search API.

**Request body:**
```json
{
  "model": "tavily",
  "query": "latest AI news",
  "max_results": 5,
  "search_type": "general",
  "country": "us",
  "language": "en"
}
```

**Key difference from chat/embeddings:** Provider IS the model. No
`provider/model` split. The `model` field is just the provider alias or ID.

**Providers to support:** tavily, brave-search, serper, exa, perplexity, xai,
kimi, gemini (all with `serviceKinds` containing `"webSearch"`).

**Provider-specific upstream URLs:**
- `tavily`: `POST https://api.tavily.com/search`
- `brave-search`: `GET https://api.search.brave.com/res/v1/web/search?q={query}`
- `serper`: `POST https://google.serper.dev/search`
- `exa`: `POST https://api.exa.ai/search`
- `perplexity`: Uses chat completions with search-enabled model
- `xai`: Uses chat completions with `search_parameters`
- `kimi`: Uses chat completions with web search tool

**Implementation steps:**
1. Add `POST /v1/search` route to `routers/v1_proxy.py`.
2. Parse `model` (or `provider`) from body. Validate `query` present.
3. Resolve provider ID via `_resolve_provider_alias(model)`.
4. DB lookup: find active connection for that provider.
5. Build provider-specific upstream URL (add `SEARCH_PROVIDER_CONFIGS` dict
   in `services/proxy.py` or inline in the router).
6. Forward sanitized body (query, max_results, search_type, country, language,
   time_range, offset, domain_filter).
7. Return upstream response.
8. Fallback loop on 5xx.

**Note:** Search providers have very different APIs. A `SEARCH_PROVIDER_CONFIGS`
dict mapping provider → `{url, method, body_transform}` is the cleanest approach.
Start with tavily (simplest) and serper, then add others.

**Verify:** `curl -X POST http://localhost:9000/v1/search -H "Authorization: Bearer $TOKEN" -d '{"model":"tavily","query":"FastAPI tutorial"}'`

---

### 7. `POST /v1/web/fetch`

**Original:** `src/sse/handlers/fetch.js`  
**Pattern:** Same as search — provider IS the model. Resolve provider from
`body.provider || body.model`, credential fallback loop, forward to
provider-specific fetch/extract API.

**Request body:**
```json
{
  "model": "tavily",
  "url": "https://example.com",
  "format": "markdown",
  "max_characters": 5000
}
```

**Providers to support:** tavily, exa (all with `serviceKinds` containing
`"webFetch"`).

**Provider-specific upstream URLs:**
- `tavily`: `POST https://api.tavily.com/extract` with `{"urls": [url]}`
- `exa`: `POST https://api.exa.ai/contents` with `{"ids": [url]}`

**Implementation steps:**
1. Add `POST /v1/web/fetch` route to `routers/v1_proxy.py`.
2. Parse `model` (or `provider`) and `url` from body. Validate both present.
   Validate `url` is a valid URL.
3. Resolve provider ID via `_resolve_provider_alias(model)`.
4. DB lookup: find active connection for that provider.
5. Build provider-specific upstream URL and transform body to provider format.
6. Return upstream response.
7. Fallback loop on 5xx.

**Verify:** `curl -X POST http://localhost:9000/v1/web/fetch -H "Authorization: Bearer $TOKEN" -d '{"model":"tavily","url":"https://example.com"}'`

---

### 8. `POST /v1/messages`

**Original:** `src/app/api/v1/messages/route.js`  
**Pattern:** Thin wrapper — delegates to `handleChat`. The Anthropic messages
format is auto-detected and converted by the translator layer in the original.

**In the FastAPI port:** The existing `POST /v1/chat/completions` already handles
Anthropic-format requests via the `format: "claude"` path in `_build_upstream_url`.
The `/v1/messages` endpoint just needs to be an alias that forwards to the same
handler.

**Request body:** Anthropic messages format:
```json
{
  "model": "an/claude-sonnet-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024
}
```

**Implementation steps:**
1. Add `POST /v1/messages` route to `routers/v1_proxy.py`.
2. Call the same `chat_completions` handler logic (extract to shared function
   or just duplicate the route pointing to the same function).
3. The existing proxy already handles Anthropic format — no translation needed.

**Verify:** `curl -X POST http://localhost:9000/v1/messages -H "Authorization: Bearer $TOKEN" -d '{"model":"an/claude-sonnet-4","messages":[{"role":"user","content":"hi"}],"max_tokens":100}'`

---

### 9. `POST /v1/responses`

**Original:** `src/app/api/v1/responses/route.js`  
**Pattern:** Same as `/v1/messages` — thin wrapper to `handleChat`. The OpenAI
Responses API format is auto-detected by the translator.

**In the FastAPI port:** Same approach as `/v1/messages` — alias to the chat
completions handler. The Responses API format differs slightly (uses `input`
instead of `messages`, has `previous_response_id`, etc.) but for basic porting
purposes, forwarding to the same handler is sufficient.

**Implementation steps:**
1. Add `POST /v1/responses` route to `routers/v1_proxy.py`.
2. Point to the same handler as `chat_completions`.
3. If full Responses API compatibility is needed later, add a body transformer
   that converts `input` → `messages` before forwarding.

**Verify:** `curl -X POST http://localhost:9000/v1/responses -H "Authorization: Bearer $TOKEN" -d '{"model":"openai/gpt-4o","input":"Hello"}'`

---

### 10. `GET /v1/models/{kind}`

**Original:** `src/app/api/v1/models/[kind]/route.js`  
**Pattern:** Returns models filtered by service kind (e.g. `tts`, `embedding`,
`image`). Used by CLI tools to discover available models for a specific capability.

**Request:** `GET /v1/models/tts`, `GET /v1/models/embedding`, etc.

**Response:** Same format as `GET /v1/models` but filtered to providers that
support the given `serviceKind`.

**Implementation steps:**
1. Add `GET /v1/models/{kind}` route to `routers/v1_proxy.py`.
2. Reuse the existing `list_models` logic but filter by `serviceKind`.
3. Use `PROVIDER_DEFAULTS[provider].get("serviceKinds", ["llm"])` to filter.

**Note:** The existing `GET /v1/models` already has a `kind` query param filter
added in a recent commit (`feat: add kind filter to GET /v1/models endpoint`).
Check if `GET /v1/models?kind=tts` already works — if so, this endpoint is just
a path-param alias for the same thing.

**Verify:** `curl "http://localhost:9000/v1/models/tts" -H "Authorization: Bearer $TOKEN"`

---

## Implementation Order

Implement in this order — each builds on the previous:

1. **`/v1/embeddings`** — simplest, identical pattern to chat, pure JSON in/out **[IN PROGRESS — Phase 1&2 done, testing pending]**
2. **`/v1/messages`** — trivial alias, 5 lines
3. **`/v1/responses`** — trivial alias, 5 lines
4. **`/v1/models/{kind}`** — check if already works via query param first
5. **`/v1/images/generations`** — JSON in/out, slightly different URL per provider
6. **`/v1/search`** — provider-as-model pattern, need SEARCH_PROVIDER_CONFIGS
7. **`/v1/web/fetch`** — same pattern as search, fewer providers
8. **`/v1/audio/speech`** — binary response, needs Content-Type passthrough
9. **`/v1/audio/transcriptions`** — multipart input, most different from others
10. **`/v1/audio/voices`** — depends on media-providers voices endpoints

---

## Shared Utilities to Add

All new endpoints need these helpers. Add to `services/proxy.py`:

```python
async def resolve_provider_connection(
    db: AsyncSession,
    provider_input: str,          # alias or provider ID
    service_kind: str,            # "embedding", "tts", "stt", "image", "webSearch", "webFetch"
    exclude_ids: set[str] = None,
) -> ProviderConnection | None:
    """
    Resolve a provider alias/ID to an active ProviderConnection
    that supports the given service kind.
    Used by non-chat endpoints where provider IS the model.
    """
```

This avoids duplicating the DB lookup + alias resolution in every new router.

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/routers/v1_proxy.py` | Add all new route handlers |
| `backend/app/services/proxy.py` | Add `resolve_provider_connection()` helper, add search/fetch URL configs |
| `backend/app/routers/providers/constants.py` | Verify `serviceKinds` correct for all relevant providers |

No new files needed. No DB changes. No frontend changes needed for the proxy
endpoints themselves (they are API-level, not UI-level).

---

## Verification Checklist

For each endpoint, verify in the running app (not just code):

- [~] `/v1/embeddings` — returns embedding vector array [IN PROGRESS]
- [ ] `/v1/messages` — returns Anthropic-format response
- [ ] `/v1/responses` — returns response object
- [ ] `/v1/models/{kind}` — returns filtered model list
- [ ] `/v1/images/generations` — returns image URL or b64_json
- [ ] `/v1/search` — returns search results array
- [ ] `/v1/web/fetch` — returns extracted page content
- [ ] `/v1/audio/speech` — returns binary audio file
- [ ] `/v1/audio/transcriptions` — returns transcription text
- [ ] `/v1/audio/voices` — returns voice list with model field

All endpoints must:
- Return 401 when no JWT token provided
- Return 400 on missing required fields
- Return 502 when all upstream targets fail
- Log the request in the console log buffer (via `add_log`)
