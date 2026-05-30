# Comprehensive Provider Page Audit
## 9router (Next.js Original) vs 9router-fastapi (Port)

**Date:** 2026-05-19
**Auditor:** Automated QA (kanban task t_1437aead)

---

## Executive Summary

The provider page is the heart of 9router. This audit compares every feature between the original Next.js implementation and the FastAPI+React port. The port covers ~70% of provider types but has significant gaps in:
- Provider-specific configuration fields (Azure, Cloudflare, Ollama, etc.)
- Media/service kind handling (TTS, STT, embedding, image configs)
- Several API endpoints (test-models, models DELETE, client endpoint)
- Provider constants completeness (many providers missing or simplified)

---

## 1. Provider Constants Comparison

### Provider Categories

| Category | Original Count | Ported Count | Status |
|----------|---------------|-------------|--------|
| FREE_PROVIDERS | 5 (kiro, qwen, gemini-cli, iflow, opencode) | 5 (kiro, qwen, gemini-cli, iflow, opencode) | ✅ MATCH |
| FREE_TIER_PROVIDERS | 7 (openrouter, nvidia, ollama, vertex, gemini, cloudflare-ai, byteplus) | 7 (same) | ✅ MATCH |
| OAUTH_PROVIDERS | 7 (claude, antigravity, codex, github, cursor, kilocode, cline) | 7 (same) | ✅ MATCH |
| APIKEY_PROVIDERS | ~60+ (many enabled, many commented out) | ~35 (reduced set) | ⚠️ PARTIAL |
| WEB_COOKIE_PROVIDERS | 2 (grok-web, perplexity-web) | 2 (same) | ✅ MATCH |

### Missing/Changed Providers in Port

| Provider | In Original | In Port | Notes |
|----------|------------|---------|-------|
| commandcode | ✅ | ❌ | Missing entirely |
| deepseek (alias) | ds | ds | ✅ Same |
| opencode-go | ✅ | ❌ | Missing |
| nebius | ✅ | ❌ | Missing |
| hyperbolic | ✅ | ❌ | Missing |
| deepgram | ✅ | ❌ | Missing |
| assemblyai | ✅ | ❌ | Missing |
| nanobanana | ✅ | ❌ | Missing |
| elevenlabs | ✅ | ❌ | Missing |
| cartesia | ✅ | ❌ | Missing |
| playht | ✅ | ❌ | Missing |
| local-device | ✅ | ❌ | Missing |
| google-tts | ✅ | ❌ | Missing |
| edge-tts | ✅ | ❌ | Missing |
| coqui | ✅ | ❌ | Missing |
| tortoise | ✅ | ❌ | Missing |
| inworld | ✅ | ❌ | Missing |
| voyage-ai | ✅ | ❌ | Missing |
| sdwebui | ✅ | ❌ | Missing |
| comfyui | ✅ | ❌ | Missing |
| blackbox | ✅ | ❌ | Missing |
| chutes | ✅ | ❌ | Missing |
| aws-polly | ✅ | ❌ | Missing |
| searxng | ✅ | ❌ | Missing |
| google-pse | ✅ | ❌ | Missing |
| linkup | ✅ | ❌ | Missing |
| searchapi | ✅ | ❌ | Missing |
| youcom | ✅ | ❌ | Missing |
| firecrawl | ✅ | ❌ | Missing |
| jina-reader | ✅ | ❌ | Missing |
| amazon-bedrock | ❌ (not in original) | ✅ | Added in port |
| kilo-gateway | ❌ (not in original) | ✅ | Added in port |
| volcengine | ❌ (not in original) | ✅ | Added in port |

### Provider-Specific Config Differences

| Feature | Original | Port | Gap |
|---------|----------|------|-----|
| `serviceKinds` | Full (llm, tts, stt, embedding, image, imageToText, webSearch, webFetch, video, music) | Partial (some providers have it, many don't) | ⚠️ Many providers missing serviceKinds |
| `ttsConfig` | Defined for: nvidia, gemini, openai, minimax, hyperbolic, deepgram, elevenlabs, etc. | ❌ NOT ported | 🔴 CRITICAL |
| `sttConfig` | Defined for: gemini, openai, groq, deepgram, assemblyai, huggingface | ❌ NOT ported | 🔴 CRITICAL |
| `embeddingConfig` | Defined for: openrouter, nvidia, gemini, openai, github, mistral, together, fireworks, nebius, voyage-ai, jina-ai | ❌ NOT ported | 🔴 CRITICAL |
| `imageConfig` | Defined for: fal-ai, stability-ai, black-forest-labs, recraft, runwayml | ❌ NOT ported | 🔴 CRITICAL |
| `searchConfig` | Defined for: perplexity, tavily, brave-search, serper, exa, etc. | ❌ NOT ported | 🔴 CRITICAL |
| `fetchConfig` | Defined for: tavily, exa, firecrawl, jina-reader | ❌ NOT ported | 🔴 CRITICAL |
| `searchViaChat` | Defined for: gemini, kimi, minimax, openai, xai | ❌ NOT ported | 🟡 MEDIUM |
| `thinkingConfig` | Extended (claude-style) and effort (openai-style) | ✅ Ported | ✅ OK |
| `hasProviderSpecificData` | Azure, Cloudflare, xiaomi-tokenplan, aws-polly, modal | Azure, Cloudflare, xiaomi-tokenplan, amazon-bedrock | ⚠️ PARTIAL |
| `regions` | xiaomi-tokenplan has baseUrl per region | xiaomi-tokenplan missing baseUrl per region | 🟡 MEDIUM |
| `modelsFetcher` | opencode, openrouter, kilo-gateway | opencode, kilo-gateway | ⚠️ Missing openrouter |
| `passthroughModels` | opencode, openrouter, vercel-ai-gateway, grok-web | opencode, vercel-ai-gateway, grok-web | ⚠️ Missing openrouter |
| `USAGE_SUPPORTED_PROVIDERS` | ✅ Defined | ❌ Missing | 🟡 MEDIUM |
| `USAGE_APIKEY_PROVIDERS` | ✅ Defined | ❌ Missing | 🟡 MEDIUM |

---

## 2. Frontend Page Comparison

### ProvidersPage (List Page)

| Feature | Original | Port | Status |
|---------|----------|------|--------|
| Provider cards grid | ✅ | ✅ | ✅ OK |
| Provider logo/icon | Material icons | Lucide icons | ✅ OK (different icon set) |
| Provider color | ✅ | ✅ | ✅ OK |
| Provider textIcon | ✅ | ✅ | ✅ OK |
| Search/filter | ✅ | ✅ | ✅ OK |
| Category tabs (Free, OAuth, API Key, Cookie) | ✅ | ✅ | ✅ OK |
| Add Connection button per provider | ✅ | ✅ | ✅ OK |
| Connection count badge | ✅ | ✅ | ✅ OK |
| Deprecated provider warning | ✅ | ✅ | ✅ OK |
| Provider notice/info text | ✅ | ✅ | ✅ OK |
| API key URL link | ✅ | ✅ | ✅ OK |

### ProviderDetailPage (Detail Page)

| Feature | Original | Port | Status |
|---------|----------|------|--------|
| Connection list | ✅ | ✅ | ✅ OK |
| Add Connection modal | ✅ | ✅ | ✅ OK |
| Connection toggle (enable/disable) | ✅ | ✅ | ✅ OK |
| Connection delete | ✅ | ✅ | ✅ OK |
| Connection edit | ✅ | ✅ | ✅ OK |
| Test Connection | ✅ | ✅ | ✅ OK |
| Models list per connection | ✅ | ✅ | ✅ OK |
| Add Model modal | ✅ | ✅ | ✅ OK |
| Remove Model | ✅ | ✅ | ✅ OK |
| Test Model (chat) | ✅ | ✅ | ✅ OK |
| Suggested Models | ✅ | ✅ | ✅ OK |
| Compatible Providers section | ✅ | ✅ | ✅ OK |
| Passthrough Models section | ✅ | ✅ | ✅ OK |
| Cooldown Timer | ✅ | ✅ | ✅ OK |
| Connection Row details | ✅ | ✅ | ✅ OK |
| Model Row details | ✅ | ✅ | ✅ OK |
| Provider-specific fields in Add modal | ✅ | ⚠️ PARTIAL | 🟡 Some missing |
| Bulk test connections | ✅ | ✅ | ✅ OK |

### AddApiKeyModal

| Feature | Original | Port | Status |
|---------|----------|------|--------|
| API key input | ✅ | ✅ | ✅ OK |
| Base URL input | ✅ | ✅ | ✅ OK |
| Provider-specific fields (Azure endpoint, deployment) | ✅ | ⚠️ PARTIAL | 🟡 |
| Cloudflare Account ID field | ✅ | ⚠️ PARTIAL | 🟡 |
| Ollama local URL field | ✅ | ⚠️ PARTIAL | 🟡 |
| Cookie input for cookie providers | ✅ | ✅ | ✅ OK |
| OAuth flow trigger | ✅ | ✅ | ✅ OK |
| Validation before save | ✅ | ✅ | ✅ OK |

---

## 3. Backend API Endpoint Comparison

### Original Next.js Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/providers` | GET | List all connections |
| `/api/providers` | POST | Create connection |
| `/api/providers/[id]` | GET | Get single connection |
| `/api/providers/[id]` | PUT | Update connection |
| `/api/providers/[id]` | DELETE | Delete connection |
| `/api/providers/[id]/models` | GET | List models for connection |
| `/api/providers/[id]/test` | POST | Test connection |
| `/api/providers/[id]/test-models` | POST | Test specific model |
| `/api/providers/validate` | POST | Validate provider config |
| `/api/providers/test-batch` | POST | Batch test connections |
| `/api/providers/suggested-models` | GET | Get suggested models |
| `/api/providers/client` | GET | Get client-side provider info |
| `/api/providers/kilo/free-models` | GET | Get Kilo free models |

### Ported FastAPI Endpoints

| Endpoint | Method | Status | Notes |
|----------|--------|--------|-------|
| `/providers` | GET | ✅ | Works |
| `/providers` | POST | ✅ | Works |
| `/providers/{conn_id}` | GET | ✅ | Works |
| `/providers/{conn_id}` | PATCH | ✅ | Works (PATCH vs PUT) |
| `/providers/{conn_id}` | DELETE | ✅ | Works |
| `/providers/{conn_id}/models` | GET | ✅ | Works |
| `/providers/{conn_id}/models` | DELETE | ✅ | Works (remove model) |
| `/providers/{conn_id}/test` | POST | ✅ | Works |
| `/providers/validate` | POST | ✅ | Works |
| `/providers/test-batch` | POST | ✅ | Works |
| `/providers/suggested-models` | GET | ✅ | Works |
| `/providers/client` | GET | ✅ | Works |
| `/provider-nodes` | GET | ✅ | Works |
| `/provider-nodes` | POST | ✅ | Works |
| `/provider-nodes/{id}` | DELETE | ✅ | Works |
| `/provider-nodes/{id}` | PUT | ✅ | Works |
| `/provider-nodes/validate` | POST | ✅ | Works |

### Missing Endpoints in Port

| Endpoint | Method | Impact | Notes |
|----------|--------|--------|-------|
| `/providers/{id}/test-models` | POST | 🟡 MEDIUM | Test specific model chat — frontend may call this |
| `/providers/kilo/free-models` | GET | 🟢 LOW | Kilo-specific, may not be needed |

---

## 4. Backend Validation Comparison

### Original validate/route.js

The original validation endpoint handles:
- **openai**: GET /models with Bearer token
- **anthropic**: GET /models with x-api-key header
- **google**: GET /models?key= query param
- **azure**: Custom endpoint + deployment validation
- **vertex**: Service account JSON validation
- **cookie**: Session cookie validation
- **cloudflare**: Account ID + API token validation
- **ollama**: Local URL validation

### Ported validate endpoint

The ported validation handles:
- **openai**: ✅ GET /models with Bearer token
- **anthropic**: ✅ GET /models with x-api-key header
- **google**: ✅ GET /models?key= query param
- **azure**: ✅ Custom validation
- **vertex**: ⚠️ May be partial
- **cookie**: ✅ Cookie validation
- **cloudflare**: ✅ Account ID validation
- **ollama**: ✅ Local URL validation

---

## 5. Provider-Specific Fields Gap Analysis

### Azure OpenAI
| Field | Original | Port |
|-------|----------|------|
| endpoint (e.g., https://xxx.openai.azure.com) | ✅ | ✅ |
| deployment name | ✅ | ✅ |
| api-version | ✅ | ⚠️ May be missing |
| API key | ✅ | ✅ |

### Cloudflare AI
| Field | Original | Port |
|-------|----------|------|
| Account ID | ✅ | ✅ |
| API Token | ✅ | ✅ |

### Ollama Local
| Field | Original | Port |
|-------|----------|------|
| Base URL (localhost:11434) | ✅ | ✅ |
| Custom port | ✅ | ⚠️ May be missing |

### Xiaomi Token Plan
| Field | Original | Port |
|-------|----------|------|
| Region selector (sgp/cn/ams) | ✅ | ✅ |
| Region-specific baseUrl | ✅ | ❌ Missing in port |
| API key prefix (tp-) | ✅ | ⚠️ May not validate |

### Vertex AI
| Field | Original | Port |
|-------|----------|------|
| Service Account JSON | ✅ | ✅ |
| Project ID extraction | ✅ | ⚠️ May be partial |

### Amazon Bedrock (Port only)
| Field | Original | Port |
|-------|----------|------|
| Region | N/A | ✅ |
| Access Key ID | N/A | ✅ |
| Secret Access Key | N/A | ✅ |

---

## 6. Prioritized Fix List

### 🔴 CRITICAL (Blocks core functionality)

1. **Media service configs not ported** — ttsConfig, sttConfig, embeddingConfig, imageConfig, searchConfig, fetchConfig are entirely missing from ported constants. This means TTS/STT/embedding/image/search providers show up but can't actually be configured properly.
   - Files: `frontend/src/constants/providers.js`
   - Effort: LARGE (need to port ~200 lines of config)

2. **Many providers missing from constants** — ~25 providers exist in original but not in port (deepgram, elevenlabs, voyage-ai, etc.)
   - Files: `frontend/src/constants/providers.js`
   - Effort: MEDIUM

3. **Provider-specific data fields incomplete** — Azure missing api-version, Xiaomi Token Plan missing region-specific baseUrls
   - Files: `frontend/src/pages/ProviderDetailPage.jsx`, `frontend/src/pages/ProvidersPage.jsx`
   - Effort: SMALL

### 🟡 MEDIUM (Degrades experience)

4. **USAGE_SUPPORTED_PROVIDERS / USAGE_APIKEY_PROVIDERS missing** — Quota/usage page can't show provider-specific usage
   - Files: `frontend/src/constants/providers.js`
   - Effort: SMALL

5. **modelsFetcher missing for openrouter** — OpenRouter free model fetching won't work
   - Files: `frontend/src/constants/providers.js`
   - Effort: SMALL

6. **searchViaChat config missing** — Web search via chat won't work for gemini, kimi, openai, xai
   - Files: `frontend/src/constants/providers.js`
   - Effort: SMALL

7. **test-models endpoint missing** — Individual model testing may not work from detail page
   - Files: `backend/app/routers/providers.py`
   - Effort: SMALL

8. **hiddenKinds not ported** — Some providers hide certain service kinds (e.g., huggingface hides tts)
   - Files: `frontend/src/constants/providers.js`
   - Effort: SMALL

### 🟢 LOW (Nice to have)

9. **Providers not in original but added in port** — amazon-bedrock, kilo-gateway, volcengine are port additions. Verify they work correctly.
   - Effort: SMALL (verification only)

10. **Icon system difference** — Original uses Material icons, port uses Lucide. Visual difference but functional.
    - Effort: NONE (by design)

11. **kilo/free-models endpoint missing** — May not be needed in port
    - Effort: TINY

---

## 7. Recommended Task Breakdown

### Task 1: Port ALL missing provider configs (CRITICAL)
- Port ttsConfig, sttConfig, embeddingConfig, imageConfig, searchConfig, fetchConfig, searchViaChat
- Add all ~25 missing providers to constants
- Files: `frontend/src/constants/providers.js`
- Agent: OpenClaude (large task)
- Est: 1-2 hours

### Task 2: Fix provider-specific fields in UI (MEDIUM)
- Azure: add api-version field
- Xiaomi Token Plan: add region-specific baseUrls
- Verify Cloudflare, Ollama, Vertex fields
- Files: `frontend/src/pages/ProviderDetailPage.jsx`, `frontend/src/pages/ProvidersPage.jsx`
- Agent: Qoder (medium task)
- Est: 30-60 min

### Task 3: Add missing backend endpoints (MEDIUM)
- Add `/providers/{id}/test-models` POST endpoint
- Verify validation covers all provider types
- Files: `backend/app/routers/providers.py`
- Agent: OpenCode (small task)
- Est: 30 min

### Task 4: Add USAGE constants + hiddenKinds (SMALL)
- Add USAGE_SUPPORTED_PROVIDERS, USAGE_APIKEY_PROVIDERS
- Add hiddenKinds to relevant providers
- Files: `frontend/src/constants/providers.js`
- Agent: Kilo (tiny task)
- Est: 15 min

### Task 5: Integration test all provider flows (VERIFICATION)
- Test each provider type's add connection flow
- Test connection validation for each type
- Test model fetching for each type
- Agent: Manual testing or dogfood skill
- Est: 1-2 hours

---

## 8. Summary

| Area | Coverage | Critical Gaps |
|------|----------|---------------|
| Provider Constants | ~60% | Media configs, ~25 missing providers |
| Frontend List Page | ~90% | Minor field gaps |
| Frontend Detail Page | ~85% | Provider-specific fields |
| Backend Endpoints | ~90% | test-models endpoint |
| Backend Validation | ~80% | Some provider types untested |
| Overall | **~75%** | Media service configs are the biggest gap |

**The #1 priority is porting media service configs (TTS/STT/embedding/image/search). Without these, the majority of non-LLM providers are non-functional.**
