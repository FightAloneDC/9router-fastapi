# Qoder Bug: Model Test Gagal Setelah Switch Connection (Cache Stale)

> **Status:** Fixed  
> **Tanggal:** 2026-06-09  
> **File terkait:** `backend/app/routers/providers/connections.py`  
> **Severity:** High — semua provider terdampak, bukan hanya Qoder

---

## 1. Gejala

User melaporkan pola berikut di halaman `/providers/qoder`:

1. Test model `qmodel_latest` via button di connection A → **berhasil**
2. Disable connection A, enable connection B → test model → **error "Login expired"**
3. Switch kembali ke connection A (disable B, enable A) → test model → **error "Login expired"**
4. Backend test via API langsung (`POST /providers/{id}/test`) → **berhasil** (token valid)

Token di DB tidak pernah expired. Error "Login expired" muncul hanya di UI/frontend
setelah operasi switch connection.

---

## 2. Root Cause

### Connection Cache Tidak Di-invalidate

`update_provider()` (PATCH `/providers/{id}`) mengupdate `is_active` di DB
tetapi **tidak memanggil `invalidate_connection_cache()`**.

Proxy service menggunakan in-memory cache dengan TTL 30 detik:

```python
# backend/app/services/proxy.py
_connection_cache: dict[str, tuple[list, float]] = {}
CACHE_TTL = 30  # seconds

async def get_connections_cached(db, provider_id, force_refresh=False):
    now = time.time()
    if not force_refresh and provider_id in _connection_cache:
        connections, timestamp = _connection_cache[provider_id]
        if now - timestamp < CACHE_TTL:
            return connections  # ← STALE DATA
    # ... fresh DB query
```

Cache hanya di-invalidate di 2 tempat:
- `set_connection_error()` — saat connection error tercatat
- `clear_connection_error()` — saat connection error dibersihkan

Bukan di `update_provider()`.

### Dampak pada Model Test

Flow model test (`POST /models/test`):

```
Frontend → POST /models/test { model: "qd/qoder/qmodel_latest" }
  → resolve_model_to_targets()
    → _build_target_for_provider()
      → get_connections_cached("qoder")  ← STALE CACHE
        → select_connection_for_provider()  ← pilih dari data lama
```

Setelah user disable A dan enable B:
- Cache masih menganggap A active, B tidak active
- Model test bisa salah resolve ke connection yang sudah di-disable
- Atau tidak menemukan connection sama sekali (jika B belum di-cache)

### Mengapa "Login expired"?

Qoder mengembalikan error `{"code":"105","message":"Login expired"}` (HTTP 403)
saat COSY-signed request menggunakan token yang sudah tidak valid atau
connection yang sudah tidak aktif di sisi Qoder.

Error ini muncul karena model test salah resolve ke connection yang
token-nya sudah expire di upstream Qoder (bukan di DB kita).

---

## 3. Langkah Investigasi

### 3.1 Verifikasi Token Masih Valid

```bash
# Test userinfo langsung
curl -s "https://openapi.qoder.sh/api/v1/userinfo" \
  -H "Authorization: Bearer jt-JSbNAAWAsAGziAm4TAd3DIes"
# Result: HTTP 200, user info lengkap

# Test COSY-signed model list
# (via backend python script dengan build_cosy_headers)
# Result: HTTP 200, 11 models
```

### 3.2 Verifikasi DB State

```sql
SELECT id, name, test_status,
  LEFT(data::jsonb->>'accessToken', 20) as token_prefix,
  data::jsonb->>'lastError' as last_error
FROM provider_connections WHERE provider = 'qoder';
-- All connections: test_status='connected', last_error=NULL
```

### 3.3 Verifikasi Backend Test Endpoint

```bash
curl -X POST "http://localhost:9000/providers/{id}/test" \
  -H "Authorization: Bearer $TOKEN"
# Result: {"valid": true, "latencyMs": 141}
```

### 3.4 Trace Proxy Resolution Path

```bash
# Check where invalidate_connection_cache is called
grep -rn "invalidate_connection_cache" backend/app/ --include="*.py"
# Result: hanya di set_connection_error dan clear_connection_error
# TIDAK di update_provider
```

### 3.5 Reproduce Bug

```bash
# Disable connection
curl -X PATCH "/providers/{id}" -d '{"is_active": false}'
# Immediate model test → masih bisa resolve ke connection lama (stale cache)
```

### 3.6 Verify Fix

```bash
# Setelah fix: disable connection
curl -X PATCH "/providers/{id}" -d '{"is_active": false}'
# Immediate model test → "No active connection found" (cache sudah fresh)
```

---

## 4. Solusi

### Perubahan

File: `backend/app/routers/providers/connections.py`

```python
# Tambah import
from app.services.proxy import invalidate_connection_cache

# Di update_provider(), setelah db.flush():
await db.flush()
await db.refresh(conn)

# ↓ Tambahan
invalidate_connection_cache(conn.provider)

return _connection_to_out(conn)
```

### Kenapa Ini Cukup

- `invalidate_connection_cache()` menghapus entry cache untuk provider tersebut
- Request berikutnya akan `get_connections_cached()` → cache miss → fresh DB query
- `is_active` yang baru langsung ter-reflect
- Tidak perlu `reset_connection_rotation()` karena round-robin state tidak terkait
  dengan enable/disable connection

---

## 5. Dampak

### Sebelum Fix

```
User toggle connection → DB update → cache stale (30 detik)
→ model test / chat request pakai data lama → error "Login expired"
```

### Setelah Fix

```
User toggle connection → DB update → cache invalidated
→ model test / chat request langsung pakai data baru → OK
```

### Scope

Bug ini **bukan Qoder-specific**. Semua provider yang menggunakan
connection cache (`get_connections_cached`) terdampak. Qoder paling
terasa karena:
1. Token Qoder expire lebih cepat dari provider lain
2. Qoder return error spesifik "Login expired" yang confusing
3. User Qoder sering switch antar connection (multi-account)

---

## 6. Testing

### Manual Test

1. Buka `/providers/qoder`
2. Test model `qmodel_latest` → harus OK
3. Disable connection, enable connection lain
4. Test model `qmodel_latest` → harus OK (atau "No active connection" jika yang baru belum fetch models)
5. Switch kembali → test lagi → harus OK

### Automated Check

```bash
# Pastikan backend tidak error setelah fix
docker compose -f docker-compose.dev.yml logs backend --tail=5 2>&1 | grep -i error
# Expected: no errors

# Pastikan import benar
docker compose -f docker-compose.dev.yml exec backend uv run python3 -c "
from app.routers.providers.connections import update_provider
print('Import OK')
"
```
