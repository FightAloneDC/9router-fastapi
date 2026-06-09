# Provider Feature Matrix — Comprehensive Audit

**Date:** 2026-05-19
**Source:** Code analysis of both codebases + existing AUDIT-PROVIDER-PAGE.md
**Original:** `/home/mint/dev/9router/` (Next.js)
**Ported:** `/home/mint/dev/9router-fastapi/` (FastAPI + React)

---

## How to Read This Matrix

- **Original** = exists in Next.js source
- **Ported** = exists in FastAPI+React source
- **Actually Works** = verified or inferred from code quality (YES/NO/UNTESTED/PARTIAL)
- If broken, the error/cause is listed

---

## 1. PROVIDER LIST PAGE (ProvidersPage)

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| Provider cards grid | YES | YES | YES | Grid layout with responsive breakpoints |
| Provider logo (PNG) | YES | YES | YES | `/providers/{id}.png` with text-icon fallback |
| Provider color/textIcon | YES | YES | YES | From constants |
| Search/filter providers | YES | YES | YES | Local state search, filters all categories |
| Category sections (OAuth, Free, API Key, Cookie, Compatible) | YES | YES | YES | All 5 sections rendered |
| Connection count per provider | YES | YES | YES | `getProviderStats()` computes connected/error/total |
| Error code badge (AUTH/429/5XX/RUNTIME/NET) | YES | YES | YES | `getConnectionErrorTag()` |
| Error time display | YES | YES | YES | `getRelativeTime()` |
| Toggle provider on/off | YES | YES | YES | Optimistic update with rollback |
| "Test All" per category | YES | YES | PARTIAL | Ported uses client-side `validateProvider` per conn; original uses server-side `test-batch` endpoint |
| "Test All" per provider (from detail) | YES | YES | YES | `handleBatchTest('provider', providerId)` |
| ModelAvailabilityBadge | YES | YES | YES | Component present |
| Custom Providers section (OpenAI Compatible) | YES | YES | YES | `AddOpenAICompatibleModal` |
| Custom Providers section (Anthropic Compatible) | YES | YES | YES | `AddAnthropicCompatibleModal` |
| API Key initial visible limit (20) | YES | YES | YES | `APIKEY_INITIAL_VISIBLE = 20` |
| Show all API Key toggle | YES | YES | YES | `showAllApikey` state |
| Sort by connected-first | YES | YES | YES | `sortByStats()` |
| No results empty state | YES | YES | YES | Search with no matches |
| Loading skeleton | YES | YES | YES | Pulse animation skeletons |
| Add API Key modal (from list page) | YES | YES | YES | Opens `AddKeyModal` |
| OAuth modal trigger (from list page) | YES | NO | NO | Original has OAuth flow from list; ported only has it on detail page |
| Auto-connect free providers | YES | YES | YES | `handleAutoConnect()` with `noAuth: true` |
| Provider notice/info text | YES | PARTIAL | UNTESTED | Depends on constants having `notice` field |
| Deprecated provider warning | YES | PARTIAL | UNTESTED | Depends on constants having `deprecated` field |
| API key URL link | YES | PARTIAL | UNTESTED | Depends on constants having `apiKeyUrl` field |

---

## 2. PROVIDER DETAIL PAGE (ProviderDetailPage)

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| Provider header with logo | YES | YES | YES | PNG with fallback |
| Back navigation | YES | YES | YES | `useNavigate()` |
| Connection list | YES | YES | YES | Sorted by priority |
| Connection row: name/email display | YES | YES | YES | |
| Connection row: status badge | YES | YES | YES | connected/error/disabled/untested |
| Connection row: priority arrows (up/down) | YES | YES | YES | `handleSwapPriority()` |
| Connection row: proxy pool badge | YES | YES | YES | Shows pool name |
| Connection row: cooldown timer | YES | YES | YES | `CooldownTimer` component |
| Connection row: edit button | YES | YES | YES | Opens AddKeyModal in edit mode |
| Connection row: test button | YES | YES | YES | `handleTestConnectionRow()` |
| Connection row: delete button | YES | YES | YES | With `ConfirmModal` |
| Connection row: toggle active | YES | YES | YES | Auto-save toggle |
| Connection row: proxy selector dropdown | YES | YES | YES | Inline dropdown per row |
| Add Connection button | YES | YES | YES | Opens modal based on auth type |
| Add API Key modal (detail page) | YES | YES | YES | `AddKeyModal` component |
| Edit connection (reuse AddKeyModal) | YES | YES | YES | `editConnection` prop |
| OAuth modal (detail page) | YES | YES | YES | `OAuthModal` component |
| Kiro Auth Modal | YES | YES | YES | `KiroAuthModal` |
| Cursor Auth Modal | YES | YES | YES | `CursorAuthModal` |
| GitLab Auth Modal | YES | YES | YES | `GitLabAuthModal` |
| IFlow Cookie Modal | YES | NO | NO | Original has `IFlowCookieModal`; ported uses generic AddKeyModal |
| NoAuth connect (free providers) | YES | YES | YES | `handleNoAuthConnect()` |
| Antigravity risk confirmation | YES | NO | NO | Original has `AG_RISK_STORAGE_KEY` localStorage check |
| Bulk proxy assignment | YES | YES | YES | Checkbox select + bulk modal |
| Bulk proxy: single pool to all | YES | YES | YES | `handleApplySinglePool()` |
| Bulk proxy: 1:1 round-robin | YES | YES | YES | `handleApplyOneToOne()` |
| Select all connections checkbox | YES | YES | YES | `toggleSelectAllConnections()` |
| Provider strategy (fallback) | YES | YES | YES | Round-robin toggle + sticky limit |
| Per-provider thinking mode | YES | YES | YES | auto/extended/none |
| Edit Compatible Node modal | YES | YES | YES | `EditCompatibleNodeModal` |
| Delete Compatible Node | YES | YES | YES | Cascade deletes connections |
| Confirm modal (danger variant) | YES | YES | YES | `ConfirmModal` component |

---

## 3. MODEL MANAGEMENT

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| Models list per provider | YES | YES | YES | Derived from first connection's `models` array |
| Model row: ID display | YES | YES | YES | |
| Model row: context length | YES | YES | YES | `(model.context_length / 1000).toFixed(0)k ctx` |
| Model row: full model path (copy) | YES | YES | YES | `{alias}/{modelId}` with copy button |
| Model row: alias display/edit | YES | YES | YES | Click to edit alias |
| Model row: test button | YES | YES | YES | `handleTestModel()` via `POST /models/test` |
| Model row: disable button | YES | YES | YES | `handleDisableModel()` |
| Model row: delete (custom only) | YES | YES | YES | `handleDeleteAlias()` |
| Model search/filter | YES | YES | YES | `modelSearchQuery` state |
| Fetch models from provider API | YES | YES | YES | `handleFetchModels()` calls `GET /providers/{id}/models` |
| Clear all models | YES | YES | YES | `handleClearModels()` |
| Add custom model modal | YES | YES | YES | `AddCustomModelModal` with test-before-add |
| Suggested models (fetched) | YES | YES | YES | `fetchedSuggestions` from `/providers/suggested-models` |
| Suggested models (from constants) | YES | PARTIAL | UNTESTED | `modelsFetcher` config missing for some providers |
| Passthrough models section (OpenRouter) | YES | YES | YES | `PassthroughModelsSection` |
| Compatible models section | YES | YES | YES | `CompatibleModelsSection` |
| Disabled models section | YES | YES | YES | Separate display for disabled models |
| Disable all models | YES | YES | YES | `handleDisableAll()` with confirm |
| Enable all models | YES | YES | YES | `handleEnableAll()` |
| Model aliases (CRUD) | YES | YES | YES | `PUT/DELETE /models/alias` |
| Auto-save models to all connections | YES | YES | YES | `saveModels()` updates all conns |

---

## 4. ADD CONNECTION MODAL (AddKeyModal)

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| Name field | YES | YES | YES | |
| API Key field (password toggle) | YES | YES | YES | Eye/EyeOff toggle |
| Cookie value field (cookie providers) | YES | YES | YES | Different placeholder per provider |
| Base URL field | YES | YES | YES | For compatible providers |
| Default Model field (compatible) | YES | YES | YES | Required for compatible providers |
| Priority field | YES | YES | YES | Number input |
| Proxy Pool selector | YES | YES | YES | Dropdown from proxy pools |
| Check/Validate button | YES | YES | YES | Inline validation before save |
| Validation result display | YES | YES | YES | Green check / red error |
| Skip validation checkbox | YES | YES | YES | "Save anyway" when validation fails |
| Test Connection button | YES | YES | YES | Full test with result display |
| Save/Add button | YES | YES | YES | Creates or updates connection |
| Edit mode (reuse modal) | YES | YES | YES | Pre-fills fields from existing connection |

### Provider-Specific Fields in AddKeyModal

| Provider | Field | Original | Ported | Actually Works |
|---|---|---|---|---|
| Azure | Azure Endpoint | YES | YES | YES |
| Azure | Deployment Name | YES | YES | YES |
| Azure | API Version | YES | YES | YES |
| Azure | Organization | YES | YES | YES |
| Cloudflare AI | Account ID | YES | YES | YES |
| Ollama Local | Host URL | YES | YES | YES |
| Ollama Local | Check button (no API key needed) | YES | YES | YES |
| Region providers | Region selector | YES | YES | YES |
| Region providers | Region-specific baseUrl | YES | NO | NO — `AI_PROVIDERS[providerId].regions` may not have per-region baseUrl |
| Cookie providers | Auth hint text | YES | YES | YES |
| Cookie providers | Website link | YES | YES | YES |
| Amazon Bedrock | Region + Access Key + Secret | N/A | YES | Port-only addition |
| Xiaomi Token Plan | Region selector (sgp/cn/ams) | YES | PARTIAL | Missing region-specific baseUrls |

---

## 5. CONNECTION VALIDATION (Backend)

| Validation Type | Original | Ported | Actually Works | Backend Function |
|---|---|---|---|---|
| OpenAI-compatible (GET /models Bearer) | YES | YES | YES | `_validate_openai_compatible()` |
| Anthropic (GET /models x-api-key) | YES | YES | YES | `_validate_anthropic()` |
| Google/Gemini (GET /models?key=) | YES | YES | YES | `_validate_google()` |
| Azure OpenAI (deployments endpoint) | YES | YES | YES | `_validate_azure()` |
| Cloudflare AI (chat completions test) | YES | YES | YES | `_validate_cloudflare()` |
| Vertex AI (service account JSON + probe) | YES | YES | YES | `_validate_vertex()` |
| Ollama (GET /api/tags) | YES | YES | YES | `_validate_ollama()` |
| Kilo Gateway (openai-chat) | N/A | YES | YES | `_validate_openai_chat()` |
| Cookie providers (manual) | YES | YES | YES | Returns "manual validation" message |
| OpenAI-compatible node (custom) | YES | YES | YES | Via `_test_openai_compatible()` |
| Anthropic-compatible node (custom) | YES | YES | YES | Via `_test_anthropic_compatible()` |
| Custom embedding node | N/A | YES | YES | Via `validate_provider_node()` |

---

## 6. PROVIDER NODES (Custom Compatible Providers)

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| List provider nodes | YES | YES | YES | `GET /provider-nodes` |
| Create OpenAI-compatible node | YES | YES | YES | Auto-generates ID with prefix |
| Create Anthropic-compatible node | YES | YES | YES | Auto-generates ID |
| Create custom-embedding node | YES | YES | YES | Port addition |
| Update provider node | YES | YES | YES | Syncs connections on prefix/baseUrl change |
| Delete provider node (cascade) | YES | YES | YES | Deletes associated connections |
| Validate node API key | YES | YES | YES | `POST /provider-nodes/validate` |
| Node ID generation (prefix scheme) | YES | YES | YES | `openai-compatible-{apiType}-{uuid}` |
| Base URL sanitization | YES | YES | YES | Strips trailing `/messages`, `/embeddings` |
| API type validation (chat/responses) | YES | YES | YES | Only for openai-compatible |
| EditCompatibleNodeModal (UI) | YES | YES | YES | Component exists |

---

## 7. BATCH TESTING

| Feature | Original | Ported | Actually Works | Notes |
|---|---|---|---|---|
| Batch test all connections | YES | YES | YES | `POST /providers/test-batch` mode=all |
| Batch test by provider | YES | YES | YES | mode=provider + providerId |
| Batch test API key only | YES | YES | YES | mode=apikey (non-OAuth) |
| Test results summary | YES | YES | YES | total/passed/failed |
| Test result per connection | YES | YES | YES | valid/latencyMs/error |
| Client-side batch test (list page) | NO | YES | YES | Port uses `Promise.allSettled` with `validateProvider` |
| Server-side batch test (list page) | YES | NO | N/A | Original calls `test-batch` endpoint |

**Difference:** The ported list page does client-side batch testing (calls validate per connection from browser), while the original calls a single server-side `test-batch` endpoint. Both work but the server-side approach is more efficient.

---

## 8. FETCH MODELS FROM PROVIDER API

| Provider | Original | Ported | Actually Works | Config |
|---|---|---|---|---|
| Anthropic/Claude | YES | YES | YES | `PROVIDER_MODELS_CONFIG["claude"]` |
| Google/Gemini | YES | YES | YES | `PROVIDER_MODELS_CONFIG["gemini"]` |
| OpenAI | YES | YES | YES | `PROVIDER_MODELS_CONFIG["openai"]` |
| OpenRouter | YES | YES | YES | `PROVIDER_MODELS_CONFIG["openrouter"]` |
| DeepSeek | YES | YES | YES | `PROVIDER_MODELS_CONFIG["deepseek"]` |
| Groq | YES | YES | YES | `PROVIDER_MODELS_CONFIG["groq"]` |
| xAI | YES | YES | YES | `PROVIDER_MODELS_CONFIG["xai"]` |
| Mistral | YES | YES | YES | `PROVIDER_MODELS_CONFIG["mistral"]` |
| Perplexity | YES | YES | YES | `PROVIDER_MODELS_CONFIG["perplexity"]` |
| Together | YES | YES | YES | `PROVIDER_MODELS_CONFIG["together"]` |
| Fireworks | YES | YES | YES | `PROVIDER_MODELS_CONFIG["fireworks"]` |
| Cerebras | YES | YES | YES | `PROVIDER_MODELS_CONFIG["cerebras"]` |
| Cohere | YES | YES | YES | `PROVIDER_MODELS_CONFIG["cohere"]` |
| Nebius | YES | YES | YES | `PROVIDER_MODELS_CONFIG["nebius"]` |
| SiliconFlow | YES | YES | YES | `PROVIDER_MODELS_CONFIG["siliconflow"]` |
| Hyperbolic | YES | YES | YES | `PROVIDER_MODELS_CONFIG["hyperbolic"]` |
| Ollama | YES | YES | YES | `PROVIDER_MODELS_CONFIG["ollama"]` |
| Nanobanana | YES | YES | YES | `PROVIDER_MODELS_CONFIG["nanobanana"]` |
| Chutes | YES | YES | YES | `PROVIDER_MODELS_CONFIG["chutes"]` |
| Nvidia | YES | YES | YES | `PROVIDER_MODELS_CONFIG["nvidia"]` |
| AssemblyAI | YES | YES | YES | `PROVIDER_MODELS_CONFIG["assemblyai"]` |
| Vercel AI Gateway | YES | YES | YES | `PROVIDER_MODELS_CONFIG["vercel-ai-gateway"]` |
| Alicode | YES | YES | YES | `PROVIDER_MODELS_CONFIG["alicode"]` |
| Alicode Intl | YES | YES | YES | `PROVIDER_MODELS_CONFIG["alicode-intl"]` |
| Volcengine Ark | YES | YES | YES | `PROVIDER_MODELS_CONFIG["volcengine-ark"]` |
| BytePlus | YES | YES | YES | `PROVIDER_MODELS_CONFIG["byteplus"]` |
| OpenAI-compatible (fallback) | YES | YES | YES | Generic fallback with default base URL |
| Anthropic-compatible (node) | YES | YES | YES | Via node detection |
| OpenAI-compatible (node) | YES | YES | YES | Via node detection |

---

## 9. MISSING ENDPOINTS IN PORT

| Endpoint | Method | Original | Ported | Impact | Workaround |
|---|---|---|---|---|---|
| `/providers/{id}/test-models` | POST | YES | NO | MEDIUM | Frontend uses `POST /models/test` instead |
| `/providers/kilo/free-models` | GET | YES | NO | LOW | Kilo-specific, not critical |

---

## 10. PROVIDER CONSTANTS COMPLETENESS

### Categories Present

| Category | Original Count | Ported Count | Status |
|---|---|---|---|
| OAUTH_PROVIDERS | 7 | 7 | MATCH |
| FREE_PROVIDERS | 5 | 5 | MATCH |
| FREE_TIER_PROVIDERS | 7 | 7 | MATCH |
| WEB_COOKIE_PROVIDERS | 2 | 2 | MATCH |
| APIKEY_PROVIDERS | ~60+ | ~35 | PARTIAL — many media/search/TTS providers missing |

### Missing Providers (in port)

~25 providers from the original are missing in the port, mostly media/service providers:
- TTS: elevenlabs, cartesia, playht, google-tts, edge-tts, coqui, tortoise, aws-polly
- STT: deepgram, assemblyai (partially present)
- Embedding: voyage-ai
- Image: sdwebui, comfyui, black-forest-labs, recraft, runwayml
- Search: searxng, google-pse, linkup, searchapi, youcom
- Fetch: firecrawl, jina-reader
- Other: commandcode, opencode-go, local-device, inworld, blackbox

### Missing Config Properties

| Config Property | Original | Ported | Impact |
|---|---|---|---|
| `ttsConfig` | YES | NO | TTS providers non-functional |
| `sttConfig` | YES | NO | STT providers non-functional |
| `embeddingConfig` | YES | NO | Embedding providers non-functional |
| `imageConfig` | YES | NO | Image providers non-functional |
| `searchConfig` | YES | NO | Search providers non-functional |
| `fetchConfig` | YES | NO | Fetch providers non-functional |
| `searchViaChat` | YES | NO | Web search via chat broken |
| `USAGE_SUPPORTED_PROVIDERS` | YES | NO | Usage page can't filter by provider |
| `USAGE_APIKEY_PROVIDERS` | YES | NO | Usage page can't filter API key providers |
| `hiddenKinds` | YES | NO | Some providers show wrong service kinds |

---

## 11. BACKEND API ENDPOINTS — COMPLETE LIST

### Provider Connections

| Endpoint | Method | Auth | Description | Status |
|---|---|---|---|---|
| `/providers` | GET | Yes | List all connections (sensitive data hidden) | WORKS |
| `/providers/client` | GET | Yes | List connections for dashboard (whitelist only) | WORKS |
| `/providers` | POST | Yes | Create connection (auto-validates) | WORKS |
| `/providers/{conn_id}` | GET | Yes | Get single connection | WORKS |
| `/providers/{conn_id}` | PATCH | Yes | Update connection | WORKS |
| `/providers/{conn_id}` | DELETE | Yes | Delete connection | WORKS |
| `/providers/{conn_id}/test` | POST | Yes | Test connection (lightweight API call) | WORKS |
| `/providers/{conn_id}/models` | GET | Yes | Fetch models from provider API | WORKS |
| `/providers/{conn_id}/models` | DELETE | Yes | Clear stored models + disabled models | WORKS |
| `/providers/validate` | POST | Yes | Validate provider credentials | WORKS |
| `/providers/test-batch` | POST | Yes | Batch test connections by group | WORKS |
| `/providers/suggested-models` | GET | Yes | Fetch + filter suggested models | WORKS |

### Provider Nodes

| Endpoint | Method | Auth | Description | Status |
|---|---|---|---|---|
| `/provider-nodes` | GET | Yes | List all custom provider nodes | WORKS |
| `/provider-nodes` | POST | Yes | Create custom provider node | WORKS |
| `/provider-nodes/{node_id}` | PUT | Yes | Update node (syncs connections) | WORKS |
| `/provider-nodes/{node_id}` | DELETE | Yes | Delete node (cascade deletes connections) | WORKS |
| `/provider-nodes/validate` | POST | Yes | Validate API key against compatible provider | WORKS |

### Provider Defaults (Backend)

The backend has `PROVIDER_DEFAULTS` dict with base URLs and validation types for 50+ providers. This is separate from the frontend constants and handles:
- Standard API Key providers (openai, anthropic, google, deepseek, groq, mistral, etc.)
- Claude-format providers (glm, kimi, minimax)
- Cloud/infrastructure (azure, vertex, cloudflare-ai, amazon-bedrock)
- Ollama (local + remote)
- Web search (tavily, brave-search, serper, exa)
- Media (fal-ai, stability-ai, jina-ai)
- Web cookie (grok-web, perplexity-web)
- OAuth/free (kiro, qwen, gemini-cli, iflow, opencode, claude, etc.)

---

## 12. OVERALL SUMMARY

| Area | Coverage | Actually Works | Critical Gaps |
|---|---|---|---|
| Provider List Page | ~90% | ~85% | OAuth modal from list page missing |
| Provider Detail Page | ~90% | ~85% | IFlow cookie modal, antigravity risk check |
| Add Connection Modal | ~90% | ~85% | Region-specific baseUrls missing |
| Model Management | ~95% | ~90% | Suggested models from constants incomplete |
| Connection Validation | ~95% | ~90% | All major types covered |
| Provider Nodes | ~100% | ~95% | Full CRUD + validation |
| Batch Testing | ~90% | ~85% | Client-side vs server-side difference |
| Fetch Models | ~95% | ~90% | 26 providers configured |
| Provider Constants | ~60% | ~60% | ~25 providers missing, all media configs missing |
| Backend Endpoints | ~95% | ~95% | Only test-models missing |

### Overall Provider System Health: **~80%**

**What works well:**
- Core LLM provider CRUD (create/read/update/delete)
- All validation types (OpenAI, Anthropic, Google, Azure, Cloudflare, Ollama, Vertex)
- Custom compatible providers (OpenAI/Anthropic nodes)
- Model management (fetch, add, remove, alias, disable, test)
- Batch testing
- Proxy pool assignment (single + bulk)
- Provider strategy (round-robin, sticky)

**What's broken or missing:**
- Media/service provider configs (TTS, STT, embedding, image, search, fetch) — ~25 providers
- Some UI modals (IFlow cookie, antigravity risk)
- Region-specific base URLs for some providers
- `USAGE_SUPPORTED_PROVIDERS` / `USAGE_APIKEY_PROVIDERS` constants
