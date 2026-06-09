# Missing Providers from Original 9Router

Provider yang ada di original Next.js tapi belum ada di FastAPI port.

**Source**: `/home/mint/dev/9router/src/shared/constants/providers.js`

---

## LLM Providers (APIKEY_PROVIDERS)

### 1. OpenCode Go

**ID**: `opencode-go`  
**Alias**: `ocg`  
**Category**: APIKEY_PROVIDERS  
**Website**: https://opencode.ai/auth  
**Notice**: OpenCode Go subscription: $5/mo (then $10/mo). Access to Kimi, GLM, Qwen, MiMo, MiniMax models.

**Status**: ✅ Implemented

**Implementation Details**:
- Base URL: `https://opencode.ai/zen/go/v1`
- Format: OpenAI-compatible (Bearer token)
- Models endpoint: `/models` (returns 200 without auth)
- Chat endpoint: `/chat/completions` (401 with invalid key)
- Special: MiniMax models (`minimax-m2.5`, `minimax-m2.7`) use Claude format (`/messages` + `x-api-key`) — not yet implemented

**Files Updated**:
- [x] `frontend/src/constants/providers.js` → `APIKEY_PROVIDERS`
- [x] `backend/app/routers/providers/constants.py` → `PROVIDER_DEFAULTS`
- [x] `backend/app/services/proxy.py` → `PROVIDER_CONFIGS` + alias `ocg`
- [x] `backend/app/routers/providers/models.py` → `PROVIDER_MODELS_CONFIG`

**TODO**:
- [ ] Implement MiniMax Claude format logic (optional, untuk model-specific routing)

---

### 2. Voyage AI

**ID**: `voyage-ai`  
**Alias**: `voyage`  
**Category**: APIKEY_PROVIDERS  
**Service**: Embedding  
**Website**: https://www.voyageai.com  

**Status**: ❌ Belum ada

**Action Required**:
- [ ] Tambah sebagai embedding provider
- [ ] Implementasi embedding endpoint config

---

### 3. Local Device

**ID**: `local-device`  
**Alias**: `local`  
**Category**: APIKEY_PROVIDERS  

**Status**: ❌ Belum ada

**Note**: Perlu investigasi — apa maksud "local device"?

---

## TTS Providers

### 4. Edge TTS

**ID**: `edge-tts`  
**Alias**: `edge`  
**Category**: APIKEY_PROVIDERS  
**Service**: TTS (Text-to-Speech)

**Status**: ❌ Belum ada

---

### 5. Google TTS

**ID**: `google-tts`  
**Alias**: `gtts`  
**Category**: APIKEY_PROVIDERS  
**Service**: TTS

**Status**: ❌ Belum ada

---

### 6. AWS Polly

**ID**: `aws-polly`  
**Alias**: `polly`  
**Category**: APIKEY_PROVIDERS  
**Service**: TTS  
**Website**: https://aws.amazon.com/polly/  
**Special Fields**: `accessKeyId`, `region`  
**Auth**: AWS Signature v4

**Status**: ❌ Belum ada

**Note**: Butuh AWS-specific auth implementation (sama seperti Amazon Bedrock)

---

## Web Search Providers

### 7. Google PSE

**ID**: `google-pse`  
**Alias**: `gpse`  
**Service**: Web Search  
**Website**: https://programmablesearchengine.google.com  
**Config**: 
- Base URL: `https://www.googleapis.com/customsearch/v1`
- Auth: API key via query param `key`
- Cost: $0.005/query
- Free quota: 3000/month

**Status**: ❌ Belum ada

---

## Image Generation Providers

### 8. Black Forest Labs

**ID**: `black-forest-labs`  
**Alias**: `bfl`  
**Service**: Image Generation  
**Website**: https://blackforestlabs.ai  
**Config**:
- Base URL: `https://api.bfl.ai/v1/get_result?id=ping`
- Auth: `x-key` header

**Status**: ❌ Belum ada

---

## Web Fetch Providers

### 9. Jina Reader

**ID**: `jina-reader`  
**Alias**: `jina`  
**Service**: Web Fetch (convert URL to markdown/text)  
**Website**: https://jina.ai/reader  
**Config**:
- Base URL: `https://r.jina.ai`
- Auth: Bearer token
- Free quota: 1M requests/month
- Formats: markdown, text, html

**Status**: ❌ Belum ada

**Note**: Berbeda dengan `jina-ai` (embedding provider) yang sudah ada

---

## Disabled/Commented in Original

Provider yang di-comment di original (tidak aktif):

- `inference-net` — Inference.net
- `nous-research` — Nous Research  
- `kimi-coding` — Kimi Coding

**Status**: Tidak perlu ditambahkan (disabled di original)

---

## Extra Providers in FastAPI Port (Not in Original)

Provider yang ada di FastAPI port tapi tidak ada di original:

1. **Amazon Bedrock** (`amazon-bedrock`) — AWS Bedrock LLM service
2. **Kilo Gateway** (`kilo-gateway`) — Kilo Gateway API key mode
3. **AskCodi** (`askcodi`) — AI coding assistant dengan OpenAI-compatible API, 100K free tokens

**Note**: Ini adalah penambahan di FastAPI port, bukan bug.

---

## Summary

| Category | Missing Count | Implemented | Priority |
|----------|---------------|-------------|----------|
| LLM (API Key) | 3 | 1 (opencode-go) | High |
| TTS | 3 | 0 | Low |
| Web Search | 1 | 0 | Medium |
| Image | 1 | 0 | Low |
| Web Fetch | 1 | 0 | Medium |
| **Total** | **9** | **1** | |

**Highest Priority**: ✅ `opencode-go` — sudah diimplementasi

**Next Priority**: `voyage-ai` (embedding), `google-pse` (web search), `jina-reader` (web fetch)

---

## Implementation Notes

### OpenCode Go

Implementasi selesai dengan catatan:

1. **Basic OpenAI-compatible format** sudah berfungsi untuk semua model
2. **MiniMax models** (`minimax-m2.5`, `minimax-m2.7`) di original pakai Claude format khusus:
   - Endpoint: `/messages` (bukan `/chat/completions`)
   - Auth: `x-api-key` header (bukan `Authorization: Bearer`)
   - Format: Anthropic/Claude message format
   - **Status**: Belum diimplementasi, tapi tidak critical karena basic format tetap bisa dipakai

3. **Models available** (dari `/models` endpoint):
   - Kimi: `kimi-k2.6`, `kimi-k2.5`
   - GLM: `glm-5.1`, `glm-5`
   - DeepSeek: `deepseek-v4-pro`, `deepseek-v4-flash`
   - Qwen: `qwen3.6-plus`, `qwen3.5-plus`
   - MiMo: `mimo-v2-pro`, `mimo-v2-omni`, `mimo-v2.5-pro`, `mimo-v2.5`
   - MiniMax: `minimax-m2.7`, `minimax-m2.5`
   - Hunyuan: `hy3-preview`

4. **Files modified**:
   - `frontend/src/constants/providers.js` — added to APIKEY_PROVIDERS
   - `backend/app/routers/providers/constants.py` — PROVIDER_DEFAULTS
   - `backend/app/services/proxy.py` — PROVIDER_CONFIGS + alias `ocg`
   - `backend/app/routers/providers/models.py` — PROVIDER_MODELS_CONFIG

### Remaining Providers

Provider lain yang belum diimplementasi membutuhkan:

- **TTS providers** (edge-tts, google-tts, aws-polly) — butuh TTS endpoint config + audio streaming
- **Web search** (google-pse) — butuh search API config + query param handling
- **Image** (black-forest-labs) — butuh image generation endpoint config
- **Web fetch** (jina-reader) — butuh fetch API config + markdown conversion
- **Embedding** (voyage-ai) — butuh embedding endpoint config

Semua ini butuh service-specific implementation yang berbeda dari standard LLM chat completions.
