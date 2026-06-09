# Audit: Available Models — Semua Provider Auth via API Key

Tanggal: 2026-05-20

## Ringkasan

Audit ini memeriksa semua provider dengan type Auth via API Key (APIKEY_PROVIDERS + FREE_TIER_PROVIDERS) untuk memastikan fitur Available Models berjalan konsisten. Referensi: Cerebras, Groq, Xiaomi MiMo, Kilo Gateway — semua sudah fix.

---

## Status Per Provider

### ✅ SUDAH FIX (Standard Available Models Section)

Provider ini sudah menggunakan standard model section dengan Fetch/Clear/Enable All/Disable All/Search/Disabled list:

| Provider | Backend Config | Frontend Config | Catatan |
|----------|---------------|-----------------|---------|
| Cerebras | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | Referensi fix |
| Groq | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | Referensi fix |
| Xiaomi MiMo | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | Referensi fix |
| Kilo Gateway | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | Referensi fix |
| OpenAI | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Anthropic | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| DeepSeek | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Mistral | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Together | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Fireworks | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Perplexity | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Cohere | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| xAI | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Hugging Face | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| SiliconFlow | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| NVIDIA NIM | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Vercel AI Gateway | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| GLM Coding | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| GLM (China) | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Kimi | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Minimax Coding | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Minimax (China) | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Alibaba | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Alibaba Intl | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Xiaomi Token Plan | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Volcengine Ark | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Volcengine | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| BytePlus | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Gemini | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Tavily | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Brave Search | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Serper | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Exa | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Fal.ai | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Stability AI | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Jina AI | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |
| Ollama Local | ✅ PROVIDER_MODELS_CONFIG | ✅ Standard | — |

### 🔧 BARU DIFIX (OpenRouter)

| Provider | Issue | Fix |
|----------|-------|-----|
| OpenRouter | Dipaksa ke `PassthroughModelsSection` via hardcoded `isOpenRouter` check | ✅ Sudah dihapus — sekarang pakai standard section |

### ⚠️ PERLU PERHATIAN (hasProviderSpecificData)

Provider ini punya field tambahan khusus. Available Models section berjalan normal, tapi model fetching mungkin perlu penyesuaian:

| Provider | Extra Fields | Backend Config | Issue |
|----------|-------------|----------------|-------|
| Azure OpenAI | azureEndpoint, deployment, apiVersion, organization | ❌ Tidak ada di PROVIDER_MODELS_CONFIG | Model fetching pakai fallback — perlu custom config karena Azure URL format beda |
| Cloudflare AI | accountId | ❌ Tidak ada di PROVIDER_MODELS_CONFIG | Model fetching pakai fallback — URL format: `/accounts/{accountId}/ai/v1/models` |
| Amazon Bedrock | (belum jelas) | ❌ Tidak ada di PROVIDER_MODELS_CONFIG | Belum ada handling khusus di AddKeyModal |
| Xiaomi Token Plan | region | ✅ Ada di PROVIDER_MODELS_CONFIG | Sudah fix |

### ❓ PROVIDER KHUSUS (Non-Standard Auth)

| Provider | Auth Type | Issue |
|----------|-----------|-------|
| Vertex AI | Service Account JSON / API Key | ❌ Tidak ada di PROVIDER_MODELS_CONFIG. Auth berbeda (service account JSON). Model fetching tidak standar |
| Vertex Partner | Service Account JSON / API Key | ❌ Tidak ada di PROVIDER_MODELS_CONFIG. Sama dengan Vertex AI |
| Ollama Cloud | API Key (free tier) | ❌ Tidak ada di PROVIDER_MODELS_CONFIG. URL: `https://ollama.com/api/tags` format beda |

### 🔄 PASSTHROUGH MODE (Berbeda dari Standard)

Provider ini menggunakan `PassthroughModelsSection` — UI berbeda, tidak ada Fetch/Clear/Enable All/Disable All:

| Provider | Flag | modelsFetcher | Catatan |
|----------|------|---------------|---------|
| OpenCode Free | passthroughModels: true | ✅ opencode-free | By design — model list dari public API |
| Grok Web | passthroughModels: true | ❌ | By design — cookie auth, model list tidak standar |

---

## Detail Masalah

### 1. Azure OpenAI — Model Fetching

**Status**: ❌ Belum ada config di `PROVIDER_MODELS_CONFIG`

**Masalah**: Azure OpenAI punya URL format khusus:
```
{endpoint}/openai/deployments/{deployment}/models?api-version={apiVersion}
```
Bukan format standar `{baseUrl}/models`.

**Yang perlu ditambahkan** di `models.py`:
```python
"azure": {
    "url_template": "{endpoint}/openai/deployments/{deployment}/models?api-version={apiVersion}",
    "method": "GET",
    "headers": {"Content-Type": "application/json"},
    "authHeader": "api-key",
    "parseResponse": lambda data: data.get("data", []),
    "requiresProviderSpecificData": True,
}
```

**Catatan**: Azure juga butuh custom handling di `fetch_provider_models` karena URL bergantung pada `providerSpecificData` dari connection.

### 2. Cloudflare AI — Model Fetching

**Status**: ❌ Belum ada config di `PROVIDER_MODELS_CONFIG`

**Masalah**: Cloudflare AI punya URL format khusus:
```
https://api.cloudflare.com/client/v4/accounts/{accountId}/ai/v1/models
```
`accountId` diambil dari `providerSpecificData` connection.

**Yang perlu ditambahkan** di `models.py`:
```python
"cloudflare-ai": {
    "url_template": "https://api.cloudflare.com/client/v4/accounts/{accountId}/ai/v1/models",
    "method": "GET",
    "headers": {"Content-Type": "application/json"},
    "authHeader": "Authorization",
    "authPrefix": "Bearer ",
    "parseResponse": lambda data: data.get("result", []),
    "requiresProviderSpecificData": True,
}
```

### 3. Amazon Bedrock — Model Fetching

**Status**: ❌ Belum ada config, belum ada handling di AddKeyModal

**Masalah**: Bedrock butuh AWS credentials (access key + secret key + region), bukan API key standar. Model fetching pakai AWS API:
```
https://bedrock-runtime.{region}.amazonaws.com/foundation-models
```

**Rekomendasi**: Perlu investigasi lebih lanjut. Mungkin perlu provider-specific form di AddKeyModal.

### 4. Vertex AI / Vertex Partner — Model Fetching

**Status**: ❌ Belum ada config

**Masalah**: Vertex AI pakai service account JSON atau OAuth, bukan API key standar. Model fetching pakai:
```
https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/models
```

**Rekomendasi**: Vertex AI mungkin lebih cocok di kategori OAuth provider, bukan API Key.

### 5. Ollama Cloud — Model Fetching

**Status**: ❌ Belum ada config di `PROVIDER_MODELS_CONFIG`

**Masalah**: Ollama Cloud API format beda dari OpenAI-compatible:
```
https://ollama.com/api/tags → returns { models: [{ name: "..." }] }
```

**Yang perlu ditambahkan**:
```python
"ollama": {
    "url": "https://ollama.com/api/tags",
    "method": "GET",
    "headers": {"Content-Type": "application/json"},
    "parseResponse": lambda data: data.get("models", []),
}
```

**Catatan**: Config ini sudah ada untuk `ollama-local`, tapi tidak untuk `ollama` (cloud). Perlu dicek apakah URL dan response format sama.

---

## Ringkasan Perubahan yang Dibutuhkan

### Prioritas Tinggi (Blocking Available Models)

| # | Provider | File | Perubahan |
|---|----------|------|-----------|
| 1 | Azure OpenAI | `backend/app/routers/providers/models.py` | Tambah custom model fetching dengan URL template |
| 2 | Cloudflare AI | `backend/app/routers/providers/models.py` | Tambah custom model fetching dengan accountId |
| 3 | Ollama Cloud | `backend/app/routers/providers/models.py` | Tambah config (mirip ollama-local) |

### Prioritas Menengah (Butuh Investigasi)

| # | Provider | File | Perubahan |
|---|----------|------|-----------|
| 4 | Amazon Bedrock | Backend + Frontend | Butuh AWS auth handling khusus |
| 5 | Vertex AI | Backend + Frontend | Mungkin reclassify ke OAuth |
| 6 | Vertex Partner | Backend + Frontend | Sama dengan Vertex AI |

### Sudah Selesai

| # | Provider | File | Perubahan |
|---|----------|------|-----------|
| 0 | OpenRouter | `frontend/src/pages/ProviderDetailPage.jsx` | ✅ Hapus `isOpenRouter` hardcoded check |

---

## Referensi: Provider yang Sudah Fix (Pattern)

Pattern yang benar untuk standard API Key provider:

### Backend (`models.py`):
```python
"provider-id": {
    "url": "https://api.provider.com/v1/models",
    "method": "GET",
    "headers": {"Content-Type": "application/json"},
    "authHeader": "Authorization",      # atau "x-api-key" untuk Anthropic-format
    "authPrefix": "Bearer ",            # kosong untuk x-api-key
    "parseResponse": lambda data: data.get("data", []),
},
```

### Backend (`constants.py`):
```python
"provider-id": {"baseUrl": "https://api.provider.com/v1", "validationType": "openai"},
```

### Frontend (`providers.js`):
```javascript
"provider-id": {
    id: "provider-id",
    alias: "xx",
    name: "Provider Name",
    icon: "IconName",
    color: "#HEX",
    textIcon: "XX",
    website: "https://provider.com",
    notice: { apiKeyUrl: "https://provider.com/api-keys" },
    serviceKinds: ["llm"],
    // TIDAK ada passthroughModels
    // TIDAK ada modelsFetcher
},
```

### Frontend (`ProviderDetailPage.jsx`):
- Tidak perlu perubahan khusus — standard section otomatis render
- `isCompatible` check → CompatibleModelsSection
- `info?.passthroughModels` check → PassthroughModelsSection
- Default → Standard section (Fetch/Clear/Enable All/Disable All/Search/Disabled)
