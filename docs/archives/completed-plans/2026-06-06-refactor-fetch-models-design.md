# Design: Refactor fetch_models() ke Modular Provider System

Tanggal: 2026-06-06
Status: Approved

---

## Problem

File `routers/providers/models.py` berisi `PROVIDER_MODELS_CONFIG` dict besar
(~400 baris) yang mendefinisikan URL, auth header, dan response parser untuk
setiap provider. Setiap entry adalah duplikasi dari informasi yang sudah ada
di config masing-masing provider.

Draft `backend/app/providers/` sudah punya 78 sub-packages dengan per-provider
`config.py` + `models.py`, tapi:
- `models.py` di setiap provider berisi kode yang hampir identik (~40 baris)
- Config di setiap provider menduplikasi field yang sama (AUTH_HEADER, FORMAT, dll)
- Sistem baru belum terintegrasi dengan endpoint `GET /providers/{conn_id}/models`

Goal: Hapus `PROVIDER_MODELS_CONFIG`, kurangi duplikasi di 78 provider packages,
dan integrasikan `Provider` class dengan endpoint model fetching.

---

## Approach: Shared Helper + Base Config (Approach A)

### 1. Base Config

File baru: `providers/base.py`

```python
from pydantic import BaseModel

class BaseProviderConfig(BaseModel):
    PROVIDER_NAME: str
    PROVIDER_ID: str
    ALIAS: str
    BASE_URL: str
    FORMAT: str = "openai"
    VALIDATION_TYPE: str = "openai"
    SERVICE_KINDS: list[str] = []
    AUTH_HEADER: str = "Authorization"
    AUTH_PREFIX: str = "Bearer "
    EXTRA_HEADERS: dict[str, str] = {}
    AUTH_QUERY_PARAM: str = ""  # non-empty for query-param auth (e.g. Gemini)
    API_KEY: str = ""

class BaseMetadata(BaseModel):
    name: str
    color: str
    textIcon: str
```

Setiap provider `config.py` inherit dari base:
```python
from app.providers.base import BaseProviderConfig, BaseMetadata

class DeepseekConfig(BaseProviderConfig):
    PROVIDER_NAME: str = "DeepSeek"
    PROVIDER_ID: str = "deepseek"
    ALIAS: str = "ds"
    BASE_URL: str = "https://api.deepseek.com"
    SERVICE_KINDS: list[str] = ["llm"]

class DeepseekMetadata(BaseMetadata):
    name: str = "DeepSeek"
    color: str = "#0066FF"
    textIcon: str = "DS"
```

### 2. Shared Model Fetcher Helper

File baru: `providers/model_helpers.py`

Dua fungsi utama:
- `fetch_models_header_auth(config, api_key, parse_fn)` — untuk provider dengan
  header-based auth (~60+ provider)
- `fetch_models_query_auth(config, api_key, parse_fn)` — untuk provider dengan
  query-param auth (Gemini)

Default `parse_fn` adalah `parse_openai_models` yang mengembalikan
`data.get("data", [])`.

Provider yang response-nya beda tinggal override `parse_fn`.

### 3. Provider Kategorisasi

**Pola 1 — Header Auth + OpenAI response** (~55+ provider):
openai, anthropic, deepseek, groq, xai, mistral, perplexity, together,
fireworks, cerebras, cohere, nebius, siliconflow, hyperbolic, nvidia,
openrouter, opencode-go, kilocode, askcodi, vercel-ai-gateway,
alicode, alicode-intl, volcengine-ark, byteplus, volcengine,
glm, glm-cn, kimi, minimax, minimax-cn,
xiaomi-mimo, xiaomi-tokenplan, nanobanana, chutes, huggingface,
tavily, brave-search, serper, exa, fal-ai, stability-ai, jina-ai,
kilo-gateway, blackbox, commandcode, cloudflare-ai, azure, ollama,
vertex, vertex-partner, amazon-bedrock

models.py = 8 baris, panggil `fetch_models_header_auth(config)`.

**Pola 2 — Header Auth + custom parse** (5-6 provider):
elevenlabs, deepgram, jina-reader

models.py = ~20 baris, custom `parse_fn` karena response shape beda.

**Pola 3 — Query param auth + custom parse** (2 provider):
gemini, ollama-local

models.py = ~20 baris, pakai `fetch_models_query_auth`.

**Pola 4 — Special handling** (2 provider):
assemblyai (hardcoded list), qoder (COSY-signed, module terpisah)

### 4. Provider Class Update

`providers/provider.py` — perubahan kecil:
- Type hint pakai `BaseProviderConfig` / `BaseMetadata` (bukan generic `BaseModel`)
- Tambah `metadata()` method
- `_load_metadata()` cari class yang ends with "Metadata"

### 5. Endpoint Refactor

`routers/providers/models.py`:
- Hapus `PROVIDER_MODELS_CONFIG` dict (~400 baris)
- Endpoint `fetch_provider_models()` dispatch ke `Provider` class
- Helper `_fetch_node_models()` untuk custom compatible nodes
- Helper `_fetch_builtin_models()` menggunakan `Provider(provider).fetch_models(token)`
- Helper `_fetch_fallback()` menggunakan `BaseProviderConfig` langsung
  untuk provider belum dimigrasi
- `_fetch_qoder_models()` tetap special case

### 6. PROVIDER_DEFAULTS — Tidak Dihapus Sekarang

`PROVIDER_DEFAULTS` di `routers/providers/constants.py` tetap dipakai sementara
di 7 file lain (connections, helpers, testing, media_providers, v1_proxy/web,
v1_proxy/images). Migrasi ke `Provider` class dilakukan bertahap di fase
berikutnya, satu file per satu.

### 7. Testing

- Unit test `fetch_models_header_auth` dan `fetch_models_query_auth` dengan mock
- Integration test `Provider("deepseek").fetch_models(api_key)` dengan mock
- Manual test via `GET /providers/{conn_id}/models` — satu provider per satu
- Update `backend/tests/test_provider_models.py` untuk cover pola baru
- Test pelan-pelan karena provider latency

---

## Files Changed

| File | Action |
|------|--------|
| `providers/base.py` | NEW — BaseProviderConfig, BaseMetadata |
| `providers/model_helpers.py` | NEW — shared fetch helpers |
| `providers/<name>/config.py` x78 | REFACTOR — inherit BaseProviderConfig |
| `providers/<name>/models.py` x78 | REFACTOR — use shared helper |
| `providers/provider.py` | REFACTOR — type hints, metadata() method |
| `routers/providers/models.py` | REFACTOR — hapus PROVIDER_MODELS_CONFIG |
| `routers/providers/constants.py` | NO CHANGE — PROVIDER_DEFAULTS tetap |
| `tests/test_provider_models.py` | UPDATE |

## Files NOT Changed

| File | Reason |
|------|--------|
| `routers/providers/constants.py` | PROVIDER_DEFAULTS dipakai sementara |
| `routers/providers/helpers.py` | Masih pakai PROVIDER_DEFAULTS |
| `routers/providers/connections.py` | Masih pakai PROVIDER_DEFAULTS |
| `routers/providers/testing.py` | Masih pakai PROVIDER_DEFAULTS |
| `routers/media_providers.py` | Masih pakai PROVIDER_DEFAULTS |
| `__dev/` | Folder backup user — read-only permanen |

---

## Order of Execution

1. Buat `providers/base.py` (BaseProviderConfig, BaseMetadata)
2. Buat `providers/model_helpers.py` (shared fetch functions)
3. Refactor satu provider contoh (deepseek) — verifikasi pola kerja
4. Refactor semua provider yang polanya sama (~55+ provider)
5. Refactor provider dengan custom parse (elevenlabs, deepgram, gemini, dll)
6. Handle special cases (assemblyai, qoder)
7. Update `providers/provider.py` (type hints, metadata method)
8. Refactor `routers/providers/models.py` — hapus PROVIDER_MODELS_CONFIG
9. Update tests
10. Manual verification satu per satu provider
