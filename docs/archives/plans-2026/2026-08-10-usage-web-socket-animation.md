# Plan: Fix /usage?tab=overview Real-time Updates (SSE Pattern)

## Problem

Halaman `/usage?tab=overview` terasa seperti "refresh browser" setiap kali
ada request baru. Animasi connection (Provider Topology) tidak mulus.

## Root Cause

Perbandingan Node.js original vs FastAPI port:

### Node.js original (UsageStats.js)
- SSE `onmessage`: hanya merge field real-time (`activeRequests`,
  `recentRequests`, `errorProvider`, `pending`) ke state existing.
  **Tidak** melakukan REST re-fetch.
- REST fetch: hanya saat period berubah.
- SSE endpoint: kirim full stats saat connect, lalu lightweight update
  (activeRequests + recentRequests + errorProvider) on event.

### FastAPI port (UsagePage.jsx — BROKEN)
- SSE `update` event listener: **memanggil `fetchData(period)`** yang
  melakukan full REST re-fetch (stats + chart) pada setiap event.
  Ini menyebabkan "refresh browser" effect.
- SSE hanya kirim `activeRequests` — **tidak kirim** `recentRequests`
  atau `errorProvider`.
- Ada 30s polling fallback **di atas** SSE — redundan dan boros.
- `ProviderTopology.jsx` sudah punya edge animation (`animated: active`)
  dan active node glow — tapi tidak pernah ter-trigger karena data
  real-time tertimpa oleh full REST re-fetch.

## Fix Strategy

Ikuti pola Node.js original: SSE untuk lightweight real-time fields,
REST hanya untuk heavy stats saat period change.

---

## Phase 1: Backend — SSE Endpoint kirim recentRequests + errorProvider

**File:** `backend/app/routers/usage_stream.py`

**Changes:**
- Import `get_recent_requests` helper (query last 20 dari
  `request_details` table, sama seperti di `usage.py:get_usage_stats`).
- SSE `update` event payload: tambah `recentRequests` dan `errorProvider`
  di samping `activeRequests` yang sudah ada.
- `keepalive` event: sama, kirim ketiga field.

**Verify:** `curl -N "http://localhost:9000/api/usage/stream?token=..."`
harus menampilkan `recentRequests` array di payload.

---

## Phase 2: Frontend — Stop full REST re-fetch on SSE update

**File:** `frontend/src/pages/UsagePage.jsx`

**Changes:**
- SSE `update` event handler: **hapus** `fetchData(period)` call.
  Hanya update `activeRequests`, `recentRequests` (via stats merge),
  `errorProvider` dari SSE data.
- SSE `keepalive` event handler: sama, hanya update real-time fields.
- Hapus 30s polling fallback (SSE + keepalive sudah cukup).
- Tetap pertahankan REST fetch saat period berubah (sudah ada via
  `useEffect([period, fetchData, activeTab])`).

**Verify:** Buka `/usage?tab=overview`, lakukan request via
`/v1/chat/completions`. Stat cards dan chart **tidak boleh flicker**.
Provider Topology edge harus beranimasi tanpa full page refresh.

---

## Phase 3: Frontend — Pass recentRequests + errorProvider ke Topology

**File:** `frontend/src/pages/UsagePage.jsx`

**Changes:**
- `lastProvider` = `recentRequests[0]?.provider || ''` (sudah ada
  pattern ini di Node.js original).
- `errorProvider` dari SSE data.
- Pass ke `<ProviderTopology activeRequests={activeRequests}
  lastProvider={lastProvider} errorProvider={errorProvider} />`.

**Verify:** Edge di Provider Topology:
- Hijau + animasi saat provider active (sedang handle request)
- Kuning saat last provider (baru saja selesai)
- Merah saat error provider

---

## Phase 4: Bug Fixes — Recent Requests Table (found during testing)

Dua bug ditemukan saat user testing di browser:

### Bug A: Tabel Recent Requests hilang saat canvas stream

**Root cause:** SSE `keepalive` mengirim `recentRequests: []` dari ring
buffer in-memory (kosong setelah server restart). Empty array adalah
truthy → menimpa data hasil REST fetch. Komponen `RecentRequests`
return `null` saat array kosong → tabel menghilang.

**Fix (`frontend/src/pages/UsagePage.jsx`):** Guard
`data.recentRequests.length > 0` — SSE hanya boleh merge recentRequests
jika ada isinya; ring buffer kosong tidak menimpa data REST.

### Bug B: Tabel Recent Requests tidak berubah

**Root cause (2 lapis):**
1. `track_request_start` / `track_request_end` tidak pernah memanggil
   `notify_usage_update()` — SSE tidak tahu ada perubahan active request.
2. Untuk streaming, `track_request_end` dipanggil tepat setelah
   `StreamingResponse` dibuat — SEBELUM generator dikonsumsi client.
   Active request hilang dari map sebelum stream benar-benar selesai.

**Fix:**
- `backend/app/services/active_requests.py`: tambah `_notify_sse()`
  (late import untuk hindari circular import dengan `usage_stream.py`),
  dipanggil di `track_request_start` dan `track_request_end`.
- Deferral `track_request_end` ke akhir generator di semua streaming
  path (param `active_request_id` diteruskan dari caller):
  - `v1_proxy/shared.py` — `_stream_response`
  - `v1_proxy/chat.py` — `_stream_claude_response`, `_stream_grok_responses`
  - `v1_proxy/messages.py` — `_messages_stream_response`
  - `v1_proxy/responses.py` — `_stream_responses`, `_stream_responses_passthrough`
- Main handler: `track_request_end` hanya dipanggil langsung untuk
  non-streaming (`if not stream` / `if not is_stream`).
- Error paths di semua handler: `track_request_end(..., status="error")`
  agar `errorProvider` ter-set (edge merah di topology).

---

## Files Changed

| File | Change |
|------|--------|
| `backend/app/routers/usage_stream.py` | Add recentRequests + errorProvider to SSE payload |
| `backend/app/services/active_requests.py` | Ring buffer + error provider + `_notify_sse()` on start/end |
| `backend/app/services/usage_tracking.py` | `push_recent_request()` setelah DB commit |
| `backend/app/routers/v1_proxy/shared.py` | Defer `track_request_end` ke akhir generator `_stream_response` |
| `backend/app/routers/v1_proxy/chat.py` | Defer `track_request_end` (3 streaming paths); error paths `status="error"` |
| `backend/app/routers/v1_proxy/messages.py` | Defer `track_request_end`; error paths `status="error"` |
| `backend/app/routers/v1_proxy/responses.py` | Defer `track_request_end` (2 streaming paths); error paths `status="error"` |
| `backend/app/routers/v1_proxy/embeddings.py` | Error paths `status="error"` |
| `frontend/src/pages/UsagePage.jsx` | Remove full REST re-fetch on SSE; merge real-time fields only; guard empty recentRequests |

## Success Criteria

- [ ] Tidak ada "refresh browser" effect pada `/usage?tab=overview`
- [ ] Provider Topology edge beranimasi saat ada request aktif
- [ ] Recent Requests panel update real-time via SSE
- [ ] Recent Requests panel TIDAK hilang saat canvas stream
- [ ] Active request tetap terlihat selama streaming berlangsung
  (baru hilang setelah stream selesai)
- [ ] Stat cards dan chart hanya update saat period berubah (bukan saat SSE event)
- [ ] Tidak ada 30s polling fallback
