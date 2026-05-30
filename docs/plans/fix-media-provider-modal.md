# Plan: Fix MediaProviderDetailPage AddKeyModal & Available Models

**Status:** 🔴 Not started
**Goal:** Samakan AddKeyModal dan Available Models section di `MediaProviderDetailPage.jsx` dengan reference gold-standard `ProviderDetailPage.jsx` (LLM).
**Reference (gold standard):** `frontend/src/pages/ProviderDetailPage.jsx`
**Target file:** `frontend/src/pages/MediaProviderDetailPage.jsx`

---

## Background — Why This Is Broken

User klik "Add API Key" di Media Providers → modal terbuka → klik **Check** dengan API key valid → muncul error `Base URL is required`.

Akar masalah:

1. **Frontend:** Field `Base URL (optional)` selalu ditampilkan di Media modal (line 394-399), padahal di LLM modal Base URL hanya muncul jika `isCompatible === true` (line 521-533 di `ProviderDetailPage.jsx`).
2. **Backend:** `PROVIDER_DEFAULTS` di `backend/app/routers/providers/constants.py` untuk media providers (elevenlabs, deepgram, inworld, edge-tts, dst) hanya mendefinisikan `serviceKinds` — tidak ada `baseUrl` atau `validationType`.
3. **Backend:** Karena `validationType` tidak di-set, `_get_validation_type()` fallback ke `"openai"` → masuk branch "OpenAI-compatible (default)" di `testing.py` line 230-244 → wajib base_url → karena tidak ada di defaults dan tidak dikirim dari frontend → return `"Base URL is required"`.

Selain modal, **Available Models section juga divergen** dari LLM page (lihat detail di Phase 2).

---

## Phase 1 — AddKeyModal: Copy Exact JSX From LLM Reference

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx` (line 241-501)

### 1.1 Diff antara Media modal vs LLM modal

| Aspect | LLM modal (`ProviderDetailPage.jsx`) | Media modal (`MediaProviderDetailPage.jsx`) | Action |
|---|---|---|---|
| Base URL field visibility | Hanya jika `isCompatible === true` | **Selalu tampil** | Sembunyikan default; tampilkan hanya jika provider compatible |
| Default Model field | Hanya jika `isCompatible === true` | Tidak ada | Tambah, conditional sama |
| Region select | Jika `providerRegions` ada | Tidak ada | Skip — tidak relevan untuk TTS/STT |
| Cookie auth handling | Ada (`isCookie`, `info?.authHint`) | Tidak ada | Skip — tidak relevan |
| Azure / Cloudflare blocks | Ada | Tidak ada | Skip — tidak relevan |
| Test Connection button (kiri-bawah) | Ada | Ada ✓ | OK |
| Validation result + skip checkbox | Ada | Ada ✓ | OK |

### 1.2 Tentukan kapan provider Media termasuk "compatible"

Provider TTS/STT yang punya endpoint custom (user override base_url) → compatible. Provider built-in dengan endpoint hardcoded → tidak.

**Mapping (sementara, bisa di-refine):**
- **Built-in (no Base URL field)**: elevenlabs, deepgram, inworld, edge-tts, gemini, gemini-tts, minimax, minimax-cn, local-device, cartesia, playht, google-tts, coqui, tortoise, voyage-ai, assemblyai-stt, sdwebui, comfyui, bfl, replicate, searxng, firecrawl, linkup, searchapi, you-com, crawl4ai
- **Compatible (show Base URL + Default Model)**: provider node bertipe `media-compatible` atau prefix `compat-` (jika ada di future). Untuk sekarang, tidak ada — semua media provider built-in.

**Implementasi:**
```jsx
function AddKeyModal({ isOpen, providerId, provider, editConnection, onClose, onCreated, proxyPools = [], isCompatible = false }) {
  // ...
  // Hanya render Base URL + Default Model jika isCompatible
  {isCompatible && (
    <Input label="Default Model" value={defaultModel} ... />
  )}
  {isCompatible && (
    <Input label="Base URL" value={baseUrl} ... />
  )}
}
```

Untuk sekarang, `isCompatible` selalu `false` di media. Field Base URL & Default Model tidak akan tampil.

### 1.3 Update `handleValidate` & `handleSave`

Sama persis dengan pola LLM:

```jsx
const handleValidate = async () => {
  // ...
  baseUrl: baseUrl.trim() || undefined,  // undefined kalau kosong
  // ...
}
```

Tidak perlu kirim baseUrl kalau user tidak isi → backend pakai default.

### 1.4 Update `submitDisabled`

Saat ini Media:
```jsx
const submitDisabled = creating
  || (!isNoAuth && !isEdit && (!name.trim() || !apiKey.trim()))
```

Pola LLM (relevan untuk Media):
```jsx
const submitDisabled = creating
  || (!isNoAuth && !isEdit && (!name.trim() || !apiKey.trim()))
  || (isCompatible && !defaultModel.trim())
```

---

## Phase 2 — Backend: Tambah `baseUrl` + `validationType` per Media Provider

**File:** `backend/app/routers/providers/constants.py` (line 84-107)

Saat ini media providers hanya punya `serviceKinds`. Tambah `baseUrl` dan `validationType` untuk masing-masing.

### 2.1 Strategy validation per provider

Setiap provider TTS/STT punya cara validasi credential berbeda. Reuse `voice_fetchers.py` yang sudah ada.

| Provider | Upstream validation endpoint | validationType |
|---|---|---|
| elevenlabs | `GET https://api.elevenlabs.io/v1/voices` | `elevenlabs` |
| deepgram | `GET https://api.deepgram.com/v1/models` | `deepgram` |
| inworld | `GET https://api.inworld.ai/tts/v1/voices` | `inworld` |
| edge-tts | (no auth — always valid) | `noauth` |
| gemini | (uses LLM `google` validation if same key) | `google` |
| minimax | `POST https://api.minimax.io/v1/get_voice` | `minimax` |
| minimax-cn | `POST https://api.minimaxi.com/v1/get_voice` | `minimax-cn` |
| local-device | (no auth — local OS) | `noauth` |
| voyage-ai | `GET https://api.voyageai.com/v1/embeddings` (head) | `voyage` |
| assemblyai-stt | `GET https://api.assemblyai.com/v2/account` | `assemblyai` |
| (others: cartesia, playht, etc.) | tetap fallback `openai` (defer) | — |

### 2.2 Update `PROVIDER_DEFAULTS`

```python
"elevenlabs": {
    "baseUrl": "https://api.elevenlabs.io",
    "validationType": "elevenlabs",
    "serviceKinds": ["tts"]
},
"deepgram": {
    "baseUrl": "https://api.deepgram.com",
    "validationType": "deepgram",
    "serviceKinds": ["stt", "imageToText", "tts"]
},
"inworld": {
    "baseUrl": "https://api.inworld.ai",
    "validationType": "inworld",
    "serviceKinds": ["tts"]
},
"edge-tts": {
    "baseUrl": "https://speech.platform.bing.com",
    "validationType": "noauth",
    "serviceKinds": ["tts"]
},
# minimax sudah ada di line 42 (anthropic validation), pertahankan
"local-device": {
    "validationType": "noauth",
    "serviceKinds": ["tts"]
},
"voyage-ai": {
    "baseUrl": "https://api.voyageai.com",
    "validationType": "voyage",
    "serviceKinds": ["embedding"]
},
"assemblyai-stt": {
    "baseUrl": "https://api.assemblyai.com",
    "validationType": "assemblyai",
    "serviceKinds": ["stt"]
},
```

---

## Phase 3 — Backend: Validation Functions per Media Provider

**File baru:** `backend/app/services/media_validators.py`
**Modifikasi:** `backend/app/routers/providers/testing.py` (route + helper imports)

### 3.1 New file: `media_validators.py`

```python
"""Validation strategies for TTS/STT/embedding providers."""
import httpx
from app.schemas.providers import ProviderValidateResponse

async def validate_elevenlabs(api_key: str) -> ProviderValidateResponse:
    if not api_key:
        return ProviderValidateResponse(valid=False, error="API key is required")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
            if r.status_code == 200:
                count = len(r.json().get("voices", []))
                return ProviderValidateResponse(valid=True, models=[{"id": f"voices/{count}"}])
            return ProviderValidateResponse(valid=False, error=f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            return ProviderValidateResponse(valid=False, error=str(e))

async def validate_deepgram(api_key: str) -> ProviderValidateResponse:
    # GET https://api.deepgram.com/v1/models with Token auth
    ...

async def validate_inworld(api_key: str) -> ProviderValidateResponse:
    # GET https://api.inworld.ai/tts/v1/voices with Basic auth
    ...

async def validate_minimax(api_key: str, region: str = "minimax") -> ProviderValidateResponse:
    # POST get_voice
    ...

async def validate_voyage(api_key: str) -> ProviderValidateResponse:
    # POST minimal embedding
    ...

async def validate_assemblyai(api_key: str) -> ProviderValidateResponse:
    # GET account
    ...

def validate_noauth() -> ProviderValidateResponse:
    return ProviderValidateResponse(valid=True, models=None)
```

### 3.2 Update `testing.py` route

Tambah branches sebelum default OpenAI fallback:

```python
if vtype == "elevenlabs":
    return await validate_elevenlabs(body.apiKey)

if vtype == "deepgram":
    return await validate_deepgram(body.apiKey)

if vtype == "inworld":
    return await validate_inworld(body.apiKey)

if vtype in ("minimax", "minimax-cn"):
    return await validate_minimax(body.apiKey, vtype)

if vtype == "voyage":
    return await validate_voyage(body.apiKey)

if vtype == "assemblyai":
    return await validate_assemblyai(body.apiKey)

if vtype == "noauth":
    return validate_noauth()

# OpenAI-compatible (default fallback)
...
```

---

## Phase 4 — Available Models Section: Align dengan LLM

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx` (line 1351-1480)

### 4.1 Diff between LLM Available Models vs Media

| Element | LLM (`ProviderDetailPage.jsx`) | Media (`MediaProviderDetailPage.jsx`) | Action |
|---|---|---|---|
| Header "Available Models" | ✓ | ✓ | OK |
| Fetch Models button | ✓ | ✓ | OK |
| Clear Models button | ✓ | ✓ | OK |
| Enable All / Disable All | ✓ | Cuma "Enable All" | Tambah "Disable All" |
| Active models grid | ✓ | ✓ | OK |
| Search input | ✓ | ✓ | OK |
| Disabled models section | ✓ | ✓ | OK |
| **Custom Model add button** | ✓ (line 1799-1805) | ❌ | **Tambah** |
| **Custom models list** | ✓ (line 1779-1797) | ❌ | **Tambah** |
| **API Suggestions section** | ✓ | ❌ | **Tambah** (defer if too complex) |
| **Model alias support** | ✓ | ❌ | **Tambah (optional)** |
| ModelRow signature | `model, fullModel, alias, copied, onCopy, onSetAlias, onDeleteAlias, testStatus, onTest, isTesting, isCustom, isFree, onDisable, modelType, onTypeChange` | `model, fullModel, copied, onCopy, testStatus, onTest, isTesting, onDisable, modelType, onTypeChange` | Extend Media ModelRow with alias + isCustom (optional, conditional render) |

### 4.2 Implementasi minimal

1. Tambah "Disable All" button (mirror LLM line 2129-2133)
2. Tambah AddCustomModelModal (copy dari LLM line 811-896)
3. Tambah "Add Model" button di akhir grid (mirror LLM line 1799-1805)
4. Render custom models dari `modelAliases` state (perlu tambah fetch + state — copy dari LLM)

### 4.3 Defer (optional, nice-to-have, tidak blocking)

- Model alias UI per row (LLM punya `onSetAlias` + `onDeleteAlias`)
- API Suggestions section (LLM line 1807+)
- isFree badge

---

## Phase 5 — Testing

### 5.1 Modal — manual test per provider

Setelah Phase 1-3 selesai, untuk tiap provider TTS/STT/embedding:

1. Open `http://localhost:5173/media-providers/<provider>`
2. Klik "Add API Key"
3. Verifikasi:
   - Field Base URL **TIDAK MUNCUL** untuk built-in providers
   - Field Default Model **TIDAK MUNCUL**
   - Tombol Check disabled saat API key kosong
   - Klik Check dengan API key valid → response "Connection verified" (green)
   - Klik Check dengan API key invalid → response error spesifik (red), tombol "Save anyway" muncul
4. Klik Add Connection → connection masuk DB
5. Klik Edit → field terisi (kecuali apiKey kosong, sesuai pola LLM)

Provider yang harus dites:
- elevenlabs (paid — skip kalau tidak ada key)
- deepgram ✓
- inworld (paid — skip)
- edge-tts (no auth)
- gemini (sudah ada key)
- minimax (paid — skip)

### 5.2 Available Models — manual test

1. Setelah connection tersimpan, klik "Fetch Models"
2. Verifikasi grid models tampil
3. Disable satu model → masuk Disabled section
4. Klik "Disable All" → semua aktif jadi disabled
5. Klik "Enable All" → semua kembali aktif
6. Klik "Add Model" → modal AddCustomModel terbuka
7. Test custom model → save → muncul di grid

### 5.3 Regression check

- Media Providers list page tetap berfungsi
- Provider connection display di list page tidak berubah
- TTS playground tetap berfungsi setelah connection tersimpan
- LLM page (ProviderDetailPage) tidak terimbas perubahan apapun

---

## Phase 6 — Report

1. Update plan ini: status `🟢 Done` + tanggal completion + catatan
2. Catat ke `docs/porting-status.md` jika relevan
3. Verifikasi via screenshot bahwa modal Media identik (minus field yang tidak relevan) dengan modal LLM

---

## Files Changed Summary (Forecast)

| File | Change |
|---|---|
| `frontend/src/pages/MediaProviderDetailPage.jsx` | AddKeyModal: hide Base URL & Default Model conditional. Available Models: add Disable All, AddCustomModelModal, Add Model button |
| `backend/app/routers/providers/constants.py` | Add `baseUrl` + `validationType` for media providers |
| `backend/app/services/media_validators.py` | NEW — validation functions per media provider |
| `backend/app/routers/providers/testing.py` | Route new validationType branches before openai fallback |
| `docs/plans/fix-media-provider-modal.md` | Update status |

No DB migration. No new pip dependencies (httpx already available).

---

## Implementation Order

**Recommended:**
1. **Phase 1 (frontend modal)** — fix Base URL field visibility. Quick win, removes the immediate error.
2. **Phase 2 + 3 (backend)** — proper validation per provider. Quality improvement.
3. **Phase 4 (Available Models)** — align UI with LLM page. UX polish.
4. **Phase 5-6** — verify + report.

User pernah konfirmasi: implementasi 1 task at a time, doc-first per task. Selesaikan Phase 1 utuh dulu (fix + verify) sebelum lanjut Phase 2.

---

## Risk & Pitfalls

- **Memory note** says "Samakan UI/UX = COPY exact JSX from reference FIRST then adapt. Never improvise layouts." → Phase 1 harus benar-benar copy struktur JSX dari LLM modal, bukan improvisasi.
- ModelRow signature di Media simpler dari LLM — kalau extend untuk Phase 4, harus pastikan tidak break existing TTS playground integration.
- `_get_validation_type()` saat ini default `"openai"` — pastikan provider yang validationType-nya belum di-add tetap fallback aman, jangan crash.
- Phase 2 mengubah `PROVIDER_DEFAULTS` shared dengan LLM page — pastikan tambah field, bukan replace existing.

---

## Out of Scope

- Provider yang tidak ada di list 8 voice fetchers di `voice_fetchers.py` (cartesia, playht, coqui, tortoise, dst) — defer, tetap fallback openai untuk sekarang.
- Webhook/streaming validation — only sync HTTP check.
- Provider auto-discovery (auto-fetch baseUrl dari OpenAPI) — out of scope.
