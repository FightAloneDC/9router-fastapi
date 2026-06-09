# Provider API Key Validation Plan

Rencana validasi untuk 33 provider yang belum ditest.

## Status Implementasi Backend

### ✅ Sudah Lengkap di 3 File (constants.py + proxy.py + models.py)

30 provider sudah ada di semua file kunci:

| Provider | ID | Alias | Special Fields | Notes |
|----------|----|-------|----------------|-------|
| GLM Coding | `glm` | `glm` | - | |
| GLM (China) | `glm-cn` | `glm-cn` | - | |
| Kimi | `kimi` | `kimi` | - | |
| Minimax Coding | `minimax` | `minimax` | - | |
| Minimax (China) | `minimax-cn` | `minimax-cn` | - | |
| Alibaba (CN) | `alicode` | `alicode` | - | Base URL sama dengan alicode-intl (perlu fix) |
| Xiaomi MiMo (Token Plan) | `xiaomi-tokenplan` | `xmtp` | **region** | Region selector: sgp/cn/ams |
| Volcengine Ark | `volcengine-ark` | `ark` | - | |
| OpenAI | `openai` | `openai` | - | |
| Vercel AI Gateway | `vercel-ai-gateway` | `vag` | - | |
| DeepSeek | `deepseek` | `ds` | - | |
| Mistral | `mistral` | `mi` | - | |
| Together | `together` | `tg` | - | |
| Fireworks | `fireworks` | `fw` | - | |
| Perplexity | `perplexity` | `px` | - | |
| Cohere | `cohere` | `co` | - | |
| Hugging Face | `huggingface` | `hf` | - | |
| SiliconFlow | `siliconflow` | `sf` | - | |
| Anthropic | `anthropic` | `an` | - | |
| xAI | `xai` | `xai` | - | |
| Ollama Local | `ollama-local` | `ollama-local` | **baseUrl** | Host URL field (default: localhost:11434) |
| Volcengine | `volcengine` | `vk` | - | |
| Tavily | `tavily` | `tavily` | - | Web search provider |
| Brave Search | `brave-search` | `brave` | - | Web search provider |
| Serper | `serper` | `serper` | - | Web search provider |
| Exa | `exa` | `exa` | - | Web search + fetch provider |
| Fal.ai | `fal-ai` | `fal` | - | Image generation provider |
| Stability AI | `stability-ai` | `stability` | - | Image generation provider |
| Jina AI | `jina-ai` | `jina` | - | Embedding provider |
| Kilo Gateway | `kilo-gateway` | `kg` | - | |

### ⚠️ Missing di models.py (Tidak Bisa Fetch Models)

3 provider tidak ada di `PROVIDER_MODELS_CONFIG`:

| Provider | ID | Alias | Special Fields | Reason |
|----------|----|-------|----------------|--------|
| Azure OpenAI | `azure` | `az` | **azureEndpoint, deployment, apiVersion, organization** | Models per-deployment, tidak ada `/models` endpoint |
| Amazon Bedrock | `amazon-bedrock` | `bedrock` | **region, accessKeyId, secretAccessKey** | AWS-specific auth, tidak ada standard `/models` endpoint |
| Vertex Partner | `vertex-partner` | `vxp` | - | GCP service account auth, tidak ada standard endpoint |

## Checklist Validasi

### 1. URL Validation (curl test)

Untuk setiap provider, test endpoint dengan curl:

```bash
# Test chat completions endpoint (401 = OK, 404 = BROKEN)
curl -s -X POST "https://api.provider.com/v1/chat/completions" \
  -H "Authorization: Bearer test" \
  -H "Content-Type: application/json" \
  -d '{"model":"test","messages":[{"role":"user","content":"hi"}]}' \
  -w "\nHTTP:%{http_code}"

# Test models endpoint (401 = OK, 404 = BROKEN)
curl -s "https://api.provider.com/v1/models" \
  -H "Authorization: Bearer test" \
  -w "\nHTTP:%{http_code}"
```

Expected: `401 Unauthorized` (bukan `404 Not Found`)

### 2. Backend Config Validation

Cek 3 file untuk setiap provider:

- [ ] `backend/app/routers/providers/constants.py` — `PROVIDER_DEFAULTS` entry
- [ ] `backend/app/services/proxy.py` — `PROVIDER_CONFIGS` entry
- [ ] `backend/app/routers/providers/models.py` — `PROVIDER_MODELS_CONFIG` entry (kecuali azure/bedrock/vertex)

### 3. Frontend Constants Validation

Cek `frontend/src/constants/providers.js`:

- [ ] Provider ada di `APIKEY_PROVIDERS`
- [ ] Field `hasProviderSpecificData: true` jika butuh field tambahan
- [ ] Field `regions` jika butuh region selector
- [ ] Field `notice.apiKeyUrl` untuk link ke API key page

### 4. Provider-Specific Fields Implementation

#### Azure OpenAI

**Backend** (`connections.py` line 101-108):
```python
if body.provider == "azure":
    psd = body.providerSpecificData or {}
    if not psd.get("azureEndpoint"):
        raise HTTPException(status_code=400, detail="azureEndpoint is required for Azure OpenAI")
    if not psd.get("deployment"):
        raise HTTPException(status_code=400, detail="deployment is required for Azure OpenAI")
```

**Frontend** (`ProviderDetailPage.jsx` line 558-580):
```jsx
{isAzure && (
  <div className="bg-zinc-900/50 p-4 rounded-lg border border-zinc-700/40">
    <h3 className="font-semibold mb-3 text-sm text-zinc-200">Azure OpenAI Configuration</h3>
    <Input label="Azure Endpoint" ... />
    <Input label="API Version" ... />
    <Input label="Deployment Name" ... />
    <Input label="Organization (optional)" ... />
  </div>
)}
```

**Status**: ✅ Sudah diimplementasi

#### Cloudflare AI

**Backend** (`connections.py` line 109-112):
```python
if body.provider == "cloudflare-ai":
    psd = body.providerSpecificData or {}
    if not psd.get("accountId"):
        raise HTTPException(status_code=400, detail="accountId is required for Cloudflare AI")
```

**Frontend** (`ProviderDetailPage.jsx` line 543-556):
```jsx
{isCloudflareAi && (
  <div className="bg-zinc-900/50 p-4 rounded-lg border border-zinc-700/40">
    <h3 className="font-semibold mb-3 text-sm text-zinc-200">Cloudflare Configuration</h3>
    <Input label="Account ID" ... />
  </div>
)}
```

**Status**: ✅ Sudah diimplementasi

#### Ollama Local

**Frontend** (`ProviderDetailPage.jsx` line 409-429):
```jsx
{isOllamaLocal && (
  <>
    <div className="flex gap-2">
      <Input label="Host URL" ... placeholder="http://localhost:11434" />
      <Button onClick={handleValidate} ...>Check</Button>
    </div>
    <p className="text-xs text-zinc-400">
      Leave blank to use <code>http://localhost:11434</code>. For remote Ollama, enter the host URL.
    </p>
  </>
)}
```

**Status**: ✅ Sudah diimplementasi

#### Xiaomi Token Plan (Region Selector)

**Frontend constants** (`providers.js` line 60):
```javascript
"xiaomi-tokenplan": {
  ...,
  hasProviderSpecificData: true,
  regions: [
    { id: "sgp", label: "Singapore" },
    { id: "cn", label: "China" },
    { id: "ams", label: "Europe" }
  ],
  defaultRegion: "sgp"
}
```

**Frontend modal** (`ProviderDetailPage.jsx` line 233-234):
```jsx
const providerRegions = AI_PROVIDERS?.[providerId]?.regions || null
const defaultRegion = AI_PROVIDERS?.[providerId]?.defaultRegion || providerRegions?.[0]?.id || ""
```

**Status**: ⚠️ Region selector UI ada, tapi **region-specific baseUrl** belum diimplementasi

**TODO**: Tambahkan mapping region → baseUrl di backend

#### Amazon Bedrock

**Status**: ❌ Belum diimplementasi sama sekali

**TODO**:
1. Tambah field di frontend: region, accessKeyId, secretAccessKey
2. Tambah validation di backend
3. Tambah AWS signature v4 auth logic

## Action Items

### Priority 1: Fix URL yang Salah

- [x] `alicode` — sudah benar, pakai `dashscope.aliyuncs.com/compatible-mode/v1`

### Priority 2: Implementasi Region-Specific BaseURL

- [x] `xiaomi-tokenplan` — mapping region ke baseUrl:
  - `sgp` → `https://token-plan-sgp.xiaomimimo.com/v1`
  - `cn` → `https://token-plan-cn.xiaomimimo.com/v1`
  - `ams` → `https://token-plan-ams.xiaomimimo.com/v1`
  - Implementasi: `_resolve_base_url()` helper di `proxy.py` + logic khusus di `models.py`

### Priority 3: Amazon Bedrock Implementation

- [ ] Frontend: tambah 3 field (region, accessKeyId, secretAccessKey)
- [ ] Backend: AWS signature v4 auth
- [ ] Backend: region-specific endpoint construction

### Priority 4: Curl Test Semua Provider

- [x] Test 30 provider (exclude azure/bedrock/vertex)

**Hasil Test:**

✅ **25 Provider OK** (401/200 response):
- glm, glm-cn, kimi, minimax, minimax-cn, alicode, xiaomi-tokenplan
- volcengine-ark, openai, vercel-ai-gateway, deepseek, mistral
- together, cohere, siliconflow, anthropic, volcengine
- kilo-gateway
- Search providers: tavily, brave-search, serper, exa
- Image providers: fal-ai, stability-ai
- Embedding: jina-ai

⚠️ **Provider Perlu Fix:**
1. **fireworks** — chat endpoint 404 (models OK 401)
   - Current: `https://api.fireworks.ai/inference/v1`
   - Issue: `/chat/completions` tidak ada, mungkin pakai `/completions` saja
2. **perplexity** — models endpoint 404 (chat OK 401)
   - Current: `https://api.perplexity.ai`
   - Issue: tidak ada `/models` endpoint
3. **huggingface** — chat endpoint 404 (models OK 200)
   - Current: `https://api-inference.huggingface.co/v1`
   - Issue: `/chat/completions` tidak ada, mungkin pakai inference API format berbeda

❓ **Provider Perlu Investigasi:**
4. **xai** — 400 (bukan 401)
   - Mungkin butuh format request berbeda
5. **ollama-local** — 000 (localhost tidak running)
   - Normal, karena test dari server bukan localhost

## Summary

- **Priority 1**: ✅ Selesai — `alicode` sudah benar
- **Priority 2**: ✅ Selesai — `xiaomi-tokenplan` region-specific baseURL implemented
- **Priority 3**: ⏭️ Skip — Amazon Bedrock (terlalu kompleks, butuh AWS Signature v4)
- **Priority 4**: ✅ Selesai — 30 provider tested via curl

**Additional**: ✅ `opencode-go` implemented (missing provider dari original)

## Notes

### Region-Specific BaseURL Implementation

Untuk provider yang butuh region-specific URL (seperti `xiaomi-tokenplan`), implementasi dilakukan dengan:

1. **Helper function** `_resolve_base_url()` di `proxy.py`:
   - Cek custom `baseUrl` dari connection data
   - Handle region mapping untuk provider tertentu
   - Fallback ke `PROVIDER_CONFIGS`

2. **Logic khusus** di `models.py` untuk fetch models:
   - Override URL dari config berdasarkan region di `providerSpecificData`

### OpenCode Go Implementation

Provider baru yang ditambahkan dari original Next.js:

- **Base URL**: `https://opencode.ai/zen/go/v1`
- **Format**: OpenAI-compatible (Bearer token)
- **Models**: kimi-k2.6, glm-5.1, qwen3.6-plus, mimo-v2-pro, minimax-m2.7, dll
- **Special case**: MiniMax models (`minimax-m2.5`, `minimax-m2.7`) di original pakai Claude format (`/messages` + `x-api-key`), tapi belum diimplementasi di port ini — basic OpenAI format sudah cukup untuk semua model

### Provider dengan Catatan Khusus

1. **Fireworks** — chat endpoint 404 saat test dengan dummy key, perlu test dengan API key valid
2. **Perplexity** — tidak punya `/models` endpoint (by design)
3. **Hugging Face** — tidak pakai OpenAI-compatible format standard
4. **xAI** — return 400 (bukan 401), mungkin butuh format request khusus
5. **Ollama Local** — localhost endpoint, normal tidak bisa ditest dari server

### Provider Belum Diimplementasi

3 provider yang butuh implementasi khusus:

1. **Azure OpenAI** — sudah ada field UI, tapi tidak ada `/models` endpoint (per-deployment)
2. **Amazon Bedrock** — butuh AWS Signature v4 auth + region-specific endpoint
3. **Vertex Partner** — butuh GCP service account auth

### Validation Type Reference

Semua provider pakai salah satu dari validation types ini:

- `openai` — GET /models dengan Bearer token (paling umum)
- `anthropic` — GET /models dengan x-api-key header
- `google` — GET /models dengan query param `key=`
- `azure` — GET deployments endpoint dengan api-key header
- `cloudflare` — POST chat completions test dengan accountId
- `vertex` — GCP service account JSON + probe
- `ollama` — GET /api/tags
- `cookie` — manual validation (tidak bisa ditest via API)
