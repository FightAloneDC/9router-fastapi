# Plan: Media Provider Embedding — Frontend UI/UX Fix

**Status:** ✅ Done (2026-05-23) — Phase 1-5 implemented + 3 follow-up bug fixes (see § Follow-up Fixes).
**Priority:** High
**Scope:** `MediaProviderDetailPage.jsx` — halaman detail untuk Media Providers > Embedding
**Goal:** Match UI/UX dari `/providers/:providerId` (ProviderDetailPage) + Test Playground khusus embedding

---

## Background

FastAPI port punya `MediaProviderDetailPage.jsx` (509 lines) yang sangat sederhana
dibanding original Next.js (1903 lines). Test playground adalah **mock** (tidak
call API), tidak ada Models Card, tidak ada model selector, dan banyak fitur
hilang. Ini membuat halaman embedding **tidak bisa dipakai untuk testing**.

---

## Gap Analysis: Original vs FastAPI Port

### Original (Next.js) — Section Layout

```
┌─────────────────────────────────────────────┐
│ ← Back to Embedding                         │
│ [icon] Provider Name   [Get API Key →]      │
│        [EMBEDDING] [LLM]                     │
├─────────────────────────────────────────────┤
│ ⚠ Kind notice (amber, optional)             │
├─────────────────────────────────────────────┤
│ ℹ Provider notice + API key link (blue)     │
├─────────────────────────────────────────────┤
│ 🔑 Connections Card (shared component)      │
│    - Add API Key (with validation)          │
│    - Edit connection                        │
│    - Delete connection                      │
│    - Toggle active/inactive                 │
│    - Move up/down (priority)                │
│    - Proxy pool binding                     │
│    - Round Robin toggle                     │
│    - Cooldown timer                         │
│    - Error display                          │
├─────────────────────────────────────────────┤
│ 📦 Models Card (shared component)           │
│    - Show embedding models (filtered)       │
│    - Copy model ID                          │
│    - Test model                             │
│    - Add custom model                       │
│    - Delete custom model                    │
├─────────────────────────────────────────────┤
│ ℹ Provider Info Card (embeddingConfig)      │
├─────────────────────────────────────────────┤
│ 🧪 Embedding Example Card                   │
│    - Model dropdown (from fetched models)   │
│    - Endpoint input (local/tunnel)          │
│    - API Key (auto-fetch from /api/keys)    │
│    - Input text                             │
│    - Dimensions (optional)                  │
│    - Curl snippet + Copy                    │
│    - Run button (REAL API call)             │
│    - Response (compact: 4 vals + dims)      │
│    - Latency display (⚡ 234ms)             │
└─────────────────────────────────────────────┘
```

### FastAPI Port — Current State

```
┌─────────────────────────────────────────────┐
│ ← Back to Embedding                         │
│ [icon] Provider Name                         │
│        [Embedding] POST /v1/embeddings       │
├─────────────────────────────────────────────┤
│ [Left: Connections]     [Right: Test]        │
│  - Add (simplified)     - Mock playground    │
│  - Toggle active        - No model selector  │
│  - Delete               - No real API call   │
│  ❌ No edit             - No curl snippet    │
│  ❌ No priority         - No latency         │
│  ❌ No validation       - No dimensions      │
│  ❌ No proxy pool       - Hardcoded response │
└─────────────────────────────────────────────┘
❌ No Models Card
❌ No Provider Info Card
❌ No "Get API Key" link
❌ No kind notice
❌ No provider notice
```

---

## Implementation Plan

### Phase 1 — Fix TestPlayground (Paling Kritis)

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx`

**Masalah:** TestPlayground adalah mock — `handleRun` cuma `setTimeout(1000)` lalu
return `config.defaultResponse`. Tidak ada API call yang terjadi.

**Fix:**

1. **Model selector dropdown** — Ganti hardcoded `'default'` dengan dropdown yang
   menampilkan embedding models. Data dari `GET /v1/models?kind=embedding` atau
   dari connection data.

2. **Real API call** — Ganti mock `setTimeout` dengan actual `fetch('/v1/embeddings', ...)`:
   ```js
   const handleRun = async () => {
     setLoading(true)
     const start = Date.now()
     try {
       const headers = { 'Content-Type': 'application/json' }
       if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`
       const res = await fetch('/v1/embeddings', {
         method: 'POST',
         headers,
         body: JSON.stringify({
           model: selectedModel,  // e.g. "openai/text-embedding-3-small"
           input: input.trim(),
           ...(dimensions ? { dimensions: Number(dimensions) } : {}),
         }),
       })
       const latencyMs = Date.now() - start
       const data = await res.json()
       if (!res.ok) {
         setError(data?.error?.message || `HTTP ${res.status}`)
       } else {
         setResult({ data, latencyMs })
       }
     } catch (e) {
       setError(e.message)
     } finally {
       setLoading(false)
     }
   }
   ```

3. **API Key input** — Tambah field API Key yang auto-fetch dari auth store atau
   manual input. Untuk embedding proxy, JWT token user dipakai sebagai Bearer.

4. **Dimensions field** — Tambah optional input untuk `dimensions` parameter.

5. **Curl snippet** — Auto-generate curl command yang bisa di-copy:
   ```
   curl -X POST http://localhost:9000/v1/embeddings \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -d '{"model":"openai/text-embedding-3-small","input":"Hello world"}'
   ```

6. **Compact response display** — Embedding array di-compact: 4 values pertama
   + `... (1536 dims)`. Sama seperti original.

7. **Latency display** — Tampilkan `⚡ {latencyMs}ms` di atas response.

8. **Error handling** — Tampilkan error merah jika API gagal.

**Estimated:** ~150 lines changes in TestPlayground component.

---

### Phase 2 — Tambah Models Card

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx`

**Masalah:** Tidak ada cara untuk melihat embedding models yang tersedia.

**Fix:**

Tambah section baru antara Connections dan TestPlayground:

```jsx
{/* Models Section */}
<div>
  <div className="flex items-center justify-between mb-3">
    <h2 className="text-sm font-semibold text-zinc-200">
      Models — EMBEDDING
    </h2>
  </div>
  <Card>
    <div className="flex flex-wrap gap-2">
      {models.map((model) => (
        <div key={model.id} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-zinc-700 hover:border-zinc-600 transition-colors">
          <code className="text-xs font-mono text-zinc-300">
            {providerAlias}/{model.id}
          </code>
          <button onClick={() => copyModel(model.id)} className="...">
            <Copy size={12} />
          </button>
        </div>
      ))}
      {models.length === 0 && (
        <p className="text-xs text-zinc-500">No models fetched yet. Add a connection and fetch models.</p>
      )}
    </div>
  </Card>
</div>
```

**Data source:** Dari `GET /v1/models?kind=embedding` — filter models yang
prefix-nya match provider ini.

**Estimated:** ~60 lines new JSX.

---

### Phase 3 — Perbaiki Header & Info Section

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx`

**Fix:**

1. **"Get API Key" link** — Tambah di header, di samping nama provider:
   ```jsx
   {provider.apiKeyUrl && (
     <a href={provider.apiKeyUrl} target="_blank" rel="noopener noreferrer"
        className="text-xs text-blue-400 hover:underline flex items-center gap-1">
       <ExternalLink size={12} /> Get API Key
     </a>
   )}
   ```
   Perlu tambah `apiKeyUrl` di provider definitions di `constants/providers.js`.

2. **Kind badges** — Tampilkan semua serviceKinds provider, bukan cuma kind aktif:
   ```jsx
   <div className="flex gap-1.5 mt-1">
     {(provider.serviceKinds || ['llm']).map(k => (
       <Badge key={k} variant={k === kind ? 'primary' : 'default'} size="sm">
         {k.toUpperCase()}
       </Badge>
     ))}
   </div>
   ```

3. **Provider notice** — Tampilkan info box biru jika provider punya `notice.text`.

**Estimated:** ~40 lines changes.

---

### Phase 4 — Perbaiki Layout

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx`

**Masalah:** Two-column layout (Connections left, Test right) terlalu sempit
untuk test playground yang butuh banyak field.

**Fix:** Ubah ke single-column layout seperti original:

```
Connections Card (full width)
↓
Models Card (full width)
↓
Test Playground (full width)
```

Ganti `grid grid-cols-1 lg:grid-cols-2` dengan `flex flex-col gap-6`.

**Estimated:** ~10 lines CSS changes.

---

### Phase 5 — Perbaiki Connection Management

**File:** `frontend/src/pages/MediaProviderDetailPage.jsx`

**Fix yang sudah ada (pertahankan):**
- Add connection ✅
- Toggle active ✅
- Delete ✅

**Fix yang perlu ditambah:**

1. **Connection status badge** — Tampilkan test status (active/error/expired):
   ```jsx
   <Badge variant={statusVariant}>{conn.test_status || 'unknown'}</Badge>
   ```

2. **API key masking** — Tampilkan `sk-...abc` bukan `sk-...` kosong.

**Estimated:** ~30 lines changes.

---

## Files to Modify

| File | Change | Phase |
|------|--------|-------|
| `frontend/src/pages/MediaProviderDetailPage.jsx` | Fix TestPlayground, add Models, fix header, fix layout | 1-5 |
| `frontend/src/constants/providers.js` | Add `apiKeyUrl` to embedding provider definitions | 3 |
| `frontend/src/api/models.js` | Add `getModels(kind)` endpoint if not exists | 2 |

**No backend changes needed.** Semua API endpoints sudah ada:
- `GET /v1/models?kind=embedding` ✅
- `POST /v1/embeddings` ✅ (Phase 1 backend sudah selesai)
- `GET /providers/client` ✅

---

## Phase 6 — Verification

### 6.1 Visual check
1. Buka `http://localhost:5173/media-providers/embedding/openai`
2. Pastikan header tampil: icon + name + "Get API Key" + badges
3. Pastikan Connections card tampil dengan status badges
4. Pastikan Models card tampil dengan embedding models
5. Pastikan Test Playground punya: model dropdown, input, dimensions, curl, run button

### 6.2 Functional check
1. Tambah connection (API key) → pastikan muncul di list
2. Toggle active/inactive → pastikan badge berubah
3. Delete connection → pastikan hilang dari list
4. Copy model ID → pastikan clipboard terisi
5. Run test (jika ada API key aktif) → pastikan response tampil
6. Run test (tanpa API key) → pastikan error message tampil

### 6.3 Regression check
1. Buka `/media-providers/embedding` (list page) → pastikan semua provider tampil
2. Buka `/media-providers/tts/nvidia` → pastikan halaman TTS tidak rusak
3. Buka `/providers` (LLM providers) → pastikan halaman LLM tidak rusak

---

## Known Limitations

| Item | Notes |
|------|-------|
| Custom Embedding Modal | Original punya `AddCustomEmbeddingModal` untuk add custom embedding node. Belum di-port. Out of scope untuk plan ini — bisa ditambahkan nanti. |
| Tunnel support | Original punya tunnel toggle (local vs tunnel endpoint). Belum di-port. Low priority. |
| Provider Info Card | Original tampilkan `embeddingConfig` per provider. Bisa ditambahkan sebagai enhancement. |

---

## Estimated Effort

| Phase | Lines | Effort |
|-------|-------|--------|
| Phase 1 — Fix TestPlayground | ~150 | Medium |
| Phase 2 — Models Card | ~60 | Small |
| Phase 3 — Header & Info | ~40 | Small |
| Phase 4 — Layout | ~10 | Trivial |
| Phase 5 — Connection mgmt | ~30 | Small |
| **Total** | **~290** | **Medium** |

---

## Follow-up Fixes (post Phase 1-5, same-day 2026-05-23)

Setelah Phase 1-5 di-merge dan dipakai live, user lapor 3 bug. Semua fix detail-nya hidup di `docs/plans/fix-media-provider-detail-filter.md` (sister plan). Quick recap di sini supaya plan ini tetap canonical "halaman embedding sekarang ada apa":

### Fix 1 — Models section filter per `kind`

**Bug:** Page `/media-providers/embedding/<provider>` menampilkan SEMUA models (LLM + embedding + image), bukan cuma embedding.

**Fix:** Filter `models` lewat `getModelType(model.id) === kind` di `MediaProviderDetailPage.jsx`. Helper `getModelType()` (`utils/modelType.js`) infer kind dari ID (regex-based: `embed|embedding` → embedding, `tts|whisper|audio` → tts/stt, dll).

**Verified:** `/media-providers/embedding/nvidia` cuma tampil 12 embedding models (2 active, 10 disabled).

### Fix 2 — Test model button endpoint routing

**Bug:** Tombol "Test" di ModelRow embedding page POST ke `/v1/chat/completions` dengan body chat shape → upstream embedding provider reject 400.

**Fix:** Dispatch endpoint+body berdasarkan `kind` dari `useParams()`:

| Kind | Endpoint | Body |
|---|---|---|
| embedding | `/v1/embeddings` | `{model, input: 'test'}` |
| tts | `/v1/audio/speech` | `{model, input: 'test', voice: 'alloy'}` |
| image | `/v1/images/generations` | `{model, prompt: 'test', n: 1}` |
| default (llm/undefined) | `/v1/chat/completions` | `{model, messages, max_tokens: 5}` |

Default branch jaga `ProviderDetailPage.jsx` (LLM) tidak regress.

**Verified:** Live test pada nvidia → `POST /v1/embeddings` 200 OK, green check di UI.

### Fix 3 — Clipboard works in insecure context

**Bug:** Akses dashboard via HTTP LAN IP (`http://172.16.x.x:5173`) → `navigator.clipboard` undefined → klik tombol Copy lempar `TypeError: Cannot read properties of undefined (reading 'writeText')`.

**Fix:** Helper baru `frontend/src/utils/clipboard.js` dengan fallback ke legacy `document.execCommand('copy')`. Returns `Promise<boolean>`.

Patched call sites (this fix):
- `MediaProviderDetailPage.jsx`: handleCopy (ModelRow), curl snippet, response
- `ProviderDetailPage.jsx`: handleCopy

Deferred (9 call sites di OAuthModal, KiroAuthModal, SkillsPage, EndpointPage, CombosPage, CLIToolsPage) — refactor batch nanti kalau ada keluhan.

### Files touched (follow-up only)

| File | Change |
|---|---|
| `frontend/src/pages/MediaProviderDetailPage.jsx` | Filter + endpoint dispatch + clipboard helper imports |
| `frontend/src/pages/ProviderDetailPage.jsx` | Clipboard helper import |
| `frontend/src/utils/clipboard.js` | **NEW** |
| `docs/plans/fix-media-provider-detail-filter.md` | Full fix log (sections 9-11) |

---

## Cross-references

- Backend plan (sister): `docs/plans/v1-embeddings.md`
- Follow-up fix log: `docs/plans/fix-media-provider-detail-filter.md`
- Parent: `docs/plans/v1-proxy-endpoints.md` (endpoint #1)
