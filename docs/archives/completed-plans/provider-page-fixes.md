# Plan: Provider Page Fix Tasks (from Audit)

> Created: 2026-05-19
> Based on: docs/AUDIT-PROVIDER-PAGE.md (372 lines)
> Providers analysis: docs/providers-analysis.md (673 lines)

## Overview

The comprehensive audit (task t_1437aead) found ~75% coverage with these critical gaps:
- Media service configs (TTS/STT/embedding/image/search) entirely missing
- ~25 providers not ported
- Provider-specific fields incomplete
- USAGE constants and hiddenKinds missing

## Tasks (in priority order)

---

### Task 1: Port Media Service Configs + Missing Providers [CRITICAL]
- Agent: OpenClaude (large, complex task)
- File: `frontend/src/constants/providers.js`
- Reference: `/home/mint/dev/9router/src/shared/constants/providers.js`
- Est: 1-2 hours

#### What to port:
1. **ttsConfig** — add for: nvidia, gemini, openai, minimax, hyperbolic, deepgram, elevenlabs, cartesia, playht, coqui, tortoise, aws-polly, edge-tts, google-tts, inworld, local-device
2. **sttConfig** — add for: gemini, openai, groq, deepgram, assemblyai, huggingface
3. **embeddingConfig** — add for: openrouter, nvidia, gemini, openai, github, mistral, together, fireworks, nebius, voyage-ai, jina-ai
4. **imageConfig** — add for: fal-ai, stability-ai, black-forest-labs, recraft, runwayml, sdwebui, comfyui
5. **searchConfig** — add for: perplexity, tavily, brave-search, serper, exa, searxng, google-pse, linkup, searchapi, youcom
6. **fetchConfig** — add for: tavily, exa, firecrawl, jina-reader
7. **searchViaChat** — add for: gemini, kimi, minimax, openai, xai
8. **~25 missing providers** — commandcode, opencode-go, nebius, hyperbolic, deepgram, assemblyai, nanobanana, elevenlabs, cartesia, playht, local-device, google-tts, edge-tts, coqui, tortoise, inworld, voyage-ai, sdwebui, comfyui, blackbox, chutes, aws-polly, searxng, google-pse, linkup, searchapi, youcom, firecrawl, jina-reader

#### Delegation:
```
terminal(command="openclaude -p 'You are porting provider constants. Read /home/mint/dev/9router/src/shared/constants/providers.js COMPLETELY first. Then update /home/mint/dev/9router-fastapi/frontend/src/constants/providers.js to add ALL missing configs. Port these EXACTLY from the original: ttsConfig, sttConfig, embeddingConfig, imageConfig, searchConfig, fetchConfig, searchViaChat for each provider that has them. Also add ALL missing providers (commandcode, opencode-go, nebius, hyperbolic, deepgram, assemblyai, nanobanana, elevenlabs, cartesia, playht, local-device, google-tts, edge-tts, coqui, tortoise, inworld, voyage-ai, sdwebui, comfyui, blackbox, chutes, aws-polly, searxng, google-pse, linkup, searchapi, youcom, firecrawl, jina-reader). Copy their EXACT config from the original. DO NOT modify existing working provider entries. DO NOT touch any other files.' --dangerously-skip-permissions --max-turns 80", workdir="/home/mint/dev/9router-fastapi")
```

---

### Task 2: Fix Provider-Specific Fields in UI [MEDIUM]
- Agent: Qoder (medium complexity)
- Files: `frontend/src/pages/ProviderDetailPage.jsx`, `frontend/src/constants/providers.js`
- Reference: `/home/mint/dev/9router/src/app/(dashboard)/dashboard/providers/[id]/page.js`
- Est: 30-60 min
- Depends on: Task 1 (constants must be up to date first)

#### What to fix:
1. **Azure** — add `api-version` field in Add Connection modal
2. **Xiaomi Token Plan** — add region-specific baseUrls (sgp→https://sgp.api.xiaomi.com, cn→https://cn.api.xiaomi.com, ams→https://ams.api.xiaomi.com)
3. **Vertex** — verify service account JSON parsing extracts project_id correctly
4. **hasProviderSpecificData** — ensure Azure, Cloudflare, xiaomi-tokenplan, aws-polly, modal all have proper fields

#### Delegation:
```
terminal(command="qodercli -p 'Fix provider-specific fields in the 9router-fastapi port. Read /home/mint/dev/9router/src/app/\(dashboard\)/dashboard/providers/[id]/page.js and AddApiKeyModal.js for reference. In frontend/src/pages/ProviderDetailPage.jsx: (1) Add Azure api-version field to the Add Connection modal, (2) Add Xiaomi Token Plan region-specific baseUrl mapping, (3) Verify Vertex service account JSON parsing works. In frontend/src/constants/providers.js: ensure hasProviderSpecificData is set correctly for all providers that need extra fields. DO NOT touch backend files. DO NOT touch any files not mentioned.'", workdir="/home/mint/dev/9router-fastapi")
```

---

### Task 3: Add Missing Backend Endpoints [MEDIUM]
- Agent: OpenCode (small-medium task)
- File: `backend/app/routers/providers.py`
- Reference: `/home/mint/dev/9router/src/app/api/providers/[id]/test-models/route.js`
- Est: 30 min
- Depends on: None (backend only)

#### What to add:
1. **POST `/providers/{conn_id}/test-models`** — endpoint to test a specific model by sending a chat completion request
   - Request body: `{ model_id: string, message?: string }`
   - Should call the provider's chat endpoint with the model
   - Return: `{ success: bool, response: string, latency_ms: number }`

#### Delegation:
```
terminal(command="opencode run 'Add POST /providers/{conn_id}/test-models endpoint to backend/app/routers/providers.py. Read /home/mint/dev/9router/src/app/api/providers/[id]/test-models/route.js for reference implementation. The endpoint should: (1) Accept conn_id path param + model_id in body, (2) Look up the connection and its provider type, (3) Send a test chat completion to the provider using the model, (4) Return {success, response, latency_ms}. Add proper error handling. DO NOT modify any existing endpoints. DO NOT touch frontend files.' --model opencode/qwen3.6-plus-free", workdir="/home/mint/dev/9router-fastapi")
```

---

### Task 4: Add USAGE Constants + hiddenKinds [SMALL]
- Agent: Kilo (quick fix)
- File: `frontend/src/constants/providers.js`
- Reference: `/home/mint/dev/9router/src/shared/constants/providers.js`
- Est: 15 min
- Depends on: Task 1 (so we don't conflict on the same file)

#### What to add:
1. **USAGE_SUPPORTED_PROVIDERS** — array of provider IDs that support usage tracking
2. **USAGE_APIKEY_PROVIDERS** — array of API key providers that support usage
3. **hiddenKinds** — per-provider array of service kinds to hide (e.g., huggingface hides tts)

#### Delegation:
```
terminal(command="kilo run 'Add USAGE_SUPPORTED_PROVIDERS, USAGE_APIKEY_PROVIDERS constants and hiddenKinds per-provider field to frontend/src/constants/providers.js. Read /home/mint/dev/9router/src/shared/constants/providers.js for the exact values. Copy USAGE_SUPPORTED_PROVIDERS and USAGE_APIKEY_PROVIDERS arrays exactly. For providers that have hiddenKinds in the original, add that field. DO NOT modify any existing provider entries or configs. DO NOT touch any other files.' --model kilo/deepseek/deepseek-v4-flash:free", workdir="/home/mint/dev/9router-fastapi")
```

---

### Task 5: Integration Verification [LOW]
- Agent: Dogfood/manual
- Est: 1-2 hours
- Depends on: Tasks 1-4

#### What to verify:
1. Each provider category's Add Connection flow works
2. Test Connection succeeds for each provider type
3. Model fetching works for each type
4. Media providers (TTS/STT/embedding/image) show correct config fields
5. Provider-specific fields (Azure, Cloudflare, Ollama, Xiaomi) render correctly

---

## Dependency Graph
```
Task 1 (media configs + missing providers)
  └── Task 2 (provider-specific fields) ──┐
Task 3 (backend test-models endpoint) ─────┤
                                            ├── Task 5 (integration verification)
Task 4 (USAGE + hiddenKinds) ─────────────┘
```

## Execution Order
1. Task 1 + Task 3 in PARALLEL (different files, no conflict)
2. Task 2 (after Task 1 completes)
3. Task 4 (after Task 1 completes — same file)
4. Task 5 (after all above)
