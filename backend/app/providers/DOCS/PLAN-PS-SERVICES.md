# PLAN: PS Integration for backend/app/services/

Full audit: 2026-06-07
Goal: All provider-specific logic must live in `backend/app/providers/<provider>/handler.py`.
Services must be generic orchestrators only.

---

## Status Legend
- ⬜ Not started
- 🟡 In progress
- ✅ Done

---

## File 1: proxy.py ✅

**Severity:** MEDIUM (1 dead function)

**Problem:**
`build_qoder_request()` (line 522-539) — dead code, nobody calls it.
Generic `_build_provider_request()` in `v1_proxy/shared.py` already handles this.

**Fix:**
1. Delete `build_qoder_request()` function (lines 522-539)
2. Verify no imports reference it (confirmed: zero callers)

**Scope:** -18 lines, no new files
**Risk:** None — dead code removal

---

## File 2: image_adapters.py ✅

**Severity:** MEDIUM (3 adapters, mostly stubs)

**Problem:**
- `image_sdwebui()` has hardcoded path `/sdapi/v1/txt2img` (line 106)
- `IMAGE_ADAPTERS` dispatch table maps provider → adapter function directly (line 181-202)
- Most entries are stubs (`_stub_adapter`)

**Current callers:**
- `backend/app/routers/v1_proxy/images.py` — uses `IMAGE_ADAPTERS.get(provider_id)`

**Fix:**
1. Add `build_image_request()` to handler base (optional method, returns `(url, method, headers, body)`)
2. Implement in `sdwebui/handler.py` — `/sdapi/v1/txt2img` path
3. `images.py` router: try `handler.build_image_request()` first, fall back to `IMAGE_ADAPTERS` dispatch
4. Keep `IMAGE_ADAPTERS` as fallback for stubs and OpenAI-compatible (those use generic base_url)

**New files:** `backend/app/providers/sdwebui/handler.py`
**Scope:** ~+30 lines handler, ~-10 lines adapter, ~+15 lines router
**Risk:** Low — sdwebui is the only non-stub non-OpenAI-compat adapter

---

## File 3: voice_fetchers.py ✅

**Severity:** HIGH (8 providers with hardcoded URLs/auth)

**Problem:**
Each provider has its own hardcoded URL and auth pattern:
- elevenlabs: `https://api.elevenlabs.io/v1/voices`, `xi-api-key` header
- deepgram: `https://api.deepgram.com/v1/models`, `Token` prefix
- inworld: `https://api.inworld.ai/tts/v1/voices`, `Basic` prefix
- edge-tts: `https://speech.platform.bing.com/...` (no auth)
- minimax: `https://api.minimax.io/v1/get_voice` + `https://api.minimaxi.com/v1/get_voice`
- gemini: hardcoded voice list (no API)
- local-device: espeak/say subprocess

**Current callers:**
- `backend/app/routers/v1_proxy/audio.py` — uses `fetch_voices_cached()`

**Fix:**
1. Add `fetch_voices()` method to handler base (optional, returns `list[dict]`)
2. Implement per provider handler:
   - `elevenlabs/handler.py` — GET `{base_url}/voices`, xi-api-key auth
   - `deepgram/handler.py` — GET `{base_url}/models`, Token auth
   - `inworld/handler.py` — GET `{base_url}/tts/v1/voices`, Basic auth
   - `edge_tts/handler.py` — GET bing URL (no auth)
   - `minimax/handler.py` — POST `{base_url}/get_voice`, Bearer auth
   - `gemini/handler.py` — return hardcoded list
3. `voice_fetchers.py`: replace per-provider functions with generic dispatch:
   ```python
   async def fetch_voices_for_provider(client, provider, api_key, lang):
       try:
           p = Provider(provider)
           handler = p.handler()
           if hasattr(handler, "fetch_voices"):
               voices = await handler.fetch_voices(client, api_key)
               if lang:
                   voices = [v for v in voices if v.get("lang") == lang]
               return voices
       except (ValueError, ModuleNotFoundError):
           pass
       raise ValueError(f"Provider '{provider}' does not support voice listing")
   ```
4. Keep `local-device` in voice_fetchers.py (not a provider, it's OS-level)

**New files:** handlers for elevenlabs, deepgram, inworld, edge_tts, minimax, gemini
**Scope:** ~+20 lines per handler, ~-200 lines from voice_fetchers.py
**Risk:** Medium — 6 new handlers, but each is small and self-contained

---

## File 4: stt_adapters.py ✅✅✅

**Severity:** HIGH (6 providers with hardcoded URLs/auth)

**Problem:**
- deepgram: `Token` auth prefix, hardcoded `https://api.deepgram.com/v1/listen`
- gemini: hardcoded `https://generativelanguage.googleapis.com/...`, `?key=` auth
- assemblyai: hardcoded `https://api.assemblyai.com/v2`, raw key (no Bearer)
- huggingface: hardcoded `https://api-inference.huggingface.co/models`
- nvidia: hardcoded `https://integrate.api.nvidia.com/v1/audio/transcriptions`

**Current callers:**
- `backend/app/routers/v1_proxy/audio.py` — uses `get_stt_adapter()` / `STT_ADAPTERS`

**Fix:**
1. Add `build_stt_request()` to handler base (optional, returns `(url, headers, method)`)
   - Already partially done: Azure handler has `build_stt_request()`
2. Implement per provider handler:
   - `deepgram/handler.py` — Token auth, query params
   - `gemini/handler.py` — `?key=` auth, generateContent URL
   - `assemblyai/handler.py` — raw key auth, 3-step flow (complex)
   - `huggingface/handler.py` — Bearer auth, `{base}/{model}` URL
   - `nvidia/handler.py` — Bearer auth, multipart
3. `stt_adapters.py`: keep `stt_openai_compatible` as generic fallback, replace provider-specific adapters with handler dispatch
4. Keep `STT_ADAPTERS` for openai-compatible providers (openai, groq, azure)

**New files:** handlers for deepgram, gemini, assemblyai, huggingface, nvidia
**Scope:** ~+25 lines per handler, ~-150 lines from stt_adapters.py
**Risk:** Medium — assemblyai 3-step flow is complex

---

## File 5: search_adapters.py ✅

**Severity:** HIGH (10 providers with hardcoded URLs/headers/normalizers)

**Problem:**
Every search provider has hardcoded URL, auth headers, request body, AND response normalizer:
- tavily: `https://api.tavily.com/search`, Bearer
- brave: `https://api.search.brave.com/res/v1/...`, X-Subscription-Token
- serper: `https://google.serper.dev/...`, X-API-Key
- exa: `https://api.exa.ai/search`, x-api-key
- perplexity: `https://api.perplexity.ai/search`, Bearer
- google-pse: `https://www.googleapis.com/customsearch/v1`, query param key
- linkup: `https://api.linkup.so/v1/search`, Bearer
- searchapi: `https://www.searchapi.io/api/v1/search`, query param key
- youcom: `https://api.you.com/v1/search`, X-API-Key
- searxng: configurable base_url, no auth

**Current callers:**
- `backend/app/routers/v1_proxy/search.py` — uses `SEARCH_BUILDERS`, `execute_search()`

**Fix:**
1. Add `build_search_request()` and `normalize_search()` to handler base (optional)
2. Implement per provider handler (10 handlers)
3. `search_adapters.py`: replace dispatch tables with generic Provider dispatch
4. Keep shared utilities (`parse_domain_filter`, `make_result`) in search_adapters.py

**New files:** 10 handler files (tavily, brave, serper, exa, perplexity, google_pse, linkup, searchapi, youcom, searxng)
**Scope:** ~+30 lines per handler, ~-300 lines from search_adapters.py
**Risk:** High — 10 new handlers, response normalizers are provider-specific

---

## File 6: tts_adapters.py ✅

**Severity:** HIGH (14 TTS providers with hardcoded URLs/auth)

**Problem:**
Each TTS provider has its own hardcoded URL, auth pattern, and request format:
- gemini: hardcoded `https://generativelanguage.googleapis.com/...`
- elevenlabs: `https://api.elevenlabs.io/v1/text-to-speech/{voice}`, `xi-api-key`
- openrouter: `https://openrouter.ai/api/v1/chat/completions`, extra headers
- deepgram: `Token` prefix
- inworld: `Basic` prefix
- cartesia: `X-API-Key` + `Cartesia-Version` header
- playht: `X-USER-ID` + split key format
- minimax: Bearer, hex audio response
- hyperbolic: Bearer, base64 JSON response
- nvidia, huggingface: Bearer, standard binary
- edge-tts: no API key, edge_tts package

**Current callers:**
- `backend/app/routers/v1_proxy/audio.py` — uses `TTS_ADAPTERS.get(provider_id)`

**Fix:**
1. Add `build_tts_request()` to handler base (optional, returns `(url, headers, body, response_parser)`)
2. Implement per provider handler (12 new handlers, openai/siliconflow share base)
3. `tts_adapters.py`: keep `tts_openai_compatible` as generic fallback, replace dispatch table with handler dispatch
4. Keep `pcm_to_wav()` and `_format_to_mime()` as shared utilities

**New files:** 12 handler files
**Scope:** ~+35 lines per handler, ~-400 lines from tts_adapters.py
**Risk:** High — 12 new handlers, complex response parsing (hex, base64, SSE)

---

## File 7: oauth.py + oauth_providers.py ⬜

**Severity:** CRITICAL (~3400 lines duplicated across 2 files)

**Problem:**
Both files contain nearly identical OAuth config + logic for 16+ providers:
- Config dicts with hardcoded URLs (auth URL, token URL, device code URL)
- Token exchange functions
- Device code flow handlers
- Token mapping functions

**Current callers:**
- `backend/app/routers/oauth.py`
- `backend/app/services/token_refresh.py`

**Fix:** (separate plan needed — too large for this document)
1. Merge `oauth.py` and `oauth_providers.py` into one file
2. Add OAuth methods to provider handlers
3. Router becomes thin orchestrator

**Scope:** TBD (needs dedicated plan)
**Risk:** High — OAuth is critical for auth flow

---

## File 8: usage_tracking.py ⬜

**Severity:** LOW (hardcoded cost table)

**Problem:**
`_COST_TABLE` (lines 25-91) has hardcoded pricing for specific models.

**Fix:**
1. Move cost table to database or config file
2. Or keep as-is (pricing changes infrequently, low impact)

**Scope:** TBD
**Risk:** Low

---

## Execution Order

1. **proxy.py** — dead code removal, instant
2. **image_adapters.py** — small scope, 1 real adapter
3. **voice_fetchers.py** — medium scope, 6 handlers
4. **stt_adapters.py** — medium scope, 5 handlers
5. **search_adapters.py** — large scope, 10 handlers
6. **tts_adapters.py** — large scope, 12 handlers
7. **oauth.py + oauth_providers.py** — separate plan
8. **usage_tracking.py** — low priority

Each file gets its own plan section above. Execute one at a time, verify, commit, then move to next.
