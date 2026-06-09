# Qoder Bug Fixing — Full Discussion Log

Tanggal: 2026-06-06 s/d 2026-06-09 (3 hari)

---

## Daftar Isi

1. [Bug #1: Connection Switch → Stale Cache (Login Expired)](#bug-1-connection-switch--stale-cache-login-expired)
2. [Bug #2: Token Expire ~24 Jam (Bukan 30 Hari)](#bug-2-token-expire-24-jam-bukan-30-hari)
3. [Bug #3: Refresh Token Endpoint Salah (403)](#bug-3-refresh-token-endpoint-salah-403)
4. [Bug #4: Auto-Refresh Tidak Jalan untuk Idle Connection](#bug-4-auto-refresh-tidak-jalan-untuk-idle-connection)
5. [Investigasi Mendalam: Qoder Token Types](#investigasi-mendalam-qoder-token-types)
6. [Ringkasan Perubahan](#ringkasan-perubahan)
7. [Dokumen Terkait](#dokumen-terkait)

---

## Bug #1: Connection Switch → Stale Cache (Login Expired)

### Gejala

User toggle enable/disable koneksi Qoder di UI, kemudian request berikutnya gagal dengan error "Login expired" meskipun koneksi yang di-enable punya token valid.

### Root Cause

`update_provider()` di `backend/app/routers/providers/connections.py` **tidak memanggil `invalidate_connection_cache()`** setelah update DB. Proxy service punya cache 30 detik untuk connection data, jadi perubahan di DB tidak langsung ter-refleksi.

### Investigasi

```
User toggle connection → update_provider() → DB updated
                                        ↓
                              Cache masih pakai data lama (30s TTL)
                                        ↓
                              Proxy resolve → pakai koneksi lama (expired)
                                        ↓
                              "Login expired"
```

### Fix

Tambahkan `invalidate_connection_cache(conn.provider)` di `update_provider()` setelah `db.flush()` + `db.refresh(conn)`:

```python
# backend/app/routers/providers/connections.py (line ~341)
await db.flush()
await db.refresh(conn)
invalidate_connection_cache(conn.provider)  # ← TAMBAHAN
```

### File

- `backend/app/routers/providers/connections.py` — tambah import + invalidate cache

---

## Bug #2: Token Expire ~24 Jam (Bukan 30 Hari)

### Gejala

Token Qoder yang di-import via PAT (`pt-xxx`) expire dalam ~24 jam, padahal dokumentasi qodercli bilang token berlaku ~30 hari.

### Root Cause

**Token types berbeda:**

| Token Type | Prefix | Lifetime | Sumber |
|------------|--------|----------|--------|
| Device Token | `dt-` | ~30 hari | Device flow (qodercli login) |
| Job Token | `jt-` | ~24 jam | PAT exchange (`/api/v1/jobToken/exchange`) |
| Refresh Token | `jrt-` | ~48 jam | Bersama job token |

9router menggunakan PAT import → dapat **Job Token** (`jt-`) yang expire ~24 jam, bukan Device Token (`dt-`) yang ~30 hari.

### Investigasi

```bash
# qodercli menyimpan device token (dt-) di ~/.qoder/.auth/user (encrypted)
# 9router PAT exchange → /api/v1/jobToken/exchange → job token (jt-)
```

Response dari PAT exchange:
```json
{
  "token": "jt-xxx",
  "expires_in": 86400000,    // 24 jam (dalam ms)
  "refreshToken": "jrt-xxx",
  "refresh_token_expires_in": 172800000  // 48 jam
}
```

### Keputusan

Tidak implement device flow karena:
- Device flow butuh browser interaction (user harus buka URL)
- PAT exchange lebih mudah (copy-paste token)
- Dengan auto-refresh, token tidak pernah expire selama server jalan

---

## Bug #3: Refresh Token Endpoint Salah (403)

### Gejala

Semua percobaan refresh token gagal dengan HTTP 403.

### Root Cause

Endpoint refresh yang dipakai **SALAH**:

| | Salah (9router lama) | Benar (qodercli) |
|---|---|---|
| URL | `center.qoder.sh/algo/api/v3/user/refresh_token` | `openapi.qoder.sh/api/v1/jobToken/refresh` |
| Response | 403 Forbidden | 200 OK |

### Investigasi

Reverse-engineering dari `qodercli.js` (33MB bundle):

```javascript
// qodercli source (minified)
async refreshAccessTokenAsync() {
    const response = await this.httpClient.post(
        `${this.baseUrl}/api/v1/jobToken/refresh`,  // ← openapi.qoder.sh
        { refresh_token: this.cachedUserInfo.refresh_token }
    );
    // ...
}
```

### Fix

```python
# backend/app/providers/qoder/constants.py
# BEFORE:
QODER_REFRESH_TOKEN_URL = f"{QODER_CENTER_BASE}/algo/api/v3/user/refresh_token"
# AFTER:
QODER_REFRESH_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/refresh"
```

### Response Format

```json
{
  "token": "jt-xxx",
  "created_at": "2026-06-09T17:13:54Z",
  "expires_at": "2026-06-10T17:13:54Z",
  "expires_in": 86400000,
  "refresh_token": "jrt-yyy",
  "refresh_token_expires_at": "2026-06-11T17:13:54Z",
  "refresh_token_expires_in": 172800000
}
```

---

## Bug #4: Auto-Refresh Tidak Jalan untuk Idle Connection

### Gejala

Koneksi Qoder yang tidak dipakai > 24 jam expire dan tidak bisa dipakai lagi tanpa re-import PAT.

### Root Cause

Tidak ada mekanisme auto-refresh. Token hanya di-refresh saat request gagal (on-demand). Kalau tidak ada request, token expire diam-diam.

### Fix: Dual Refresh Strategy

#### 1. On-Demand Refresh (saat request gagal)

Proxy mendeteksi 401/403 dari Qoder → coba refresh → retry request (transparent ke client).

```python
# backend/app/routers/v1_proxy/chat.py
except httpx.HTTPStatusError as e:
    if e.response.status_code in (401, 403):
        from app.routers.v1_proxy.shared import _try_qoder_token_refresh
        if await _try_qoder_token_refresh(target, db):
            continue  # retry with fresh token
```

Juga saat build request gagal:
```python
except Exception as e:
    if target.provider == "qoder" and target.connection_id:
        from app.routers.v1_proxy.shared import _try_qoder_token_refresh
        if await _try_qoder_token_refresh(target, db):
            continue  # retry with fresh token
```

#### 2. Background Refresh (periodik setiap 5 menit)

Task background yang sudah ada di `token_refresh.py` dimodifikasi untuk juga me-refresh Qoder tokens:

```python
# backend/app/services/token_refresh.py
async def check_and_refresh_tokens():
    # ... existing OAuth refresh logic ...
    
    # Tambah Qoder refresh
    from app.providers.qoder.auth import refresh_all_qoder_connections
    qoder_results = await refresh_all_qoder_connections()
```

```python
# backend/app/providers/qoder/auth.py
async def refresh_all_qoder_connections() -> dict[str, bool]:
    """Background task: refresh all Qoder connections every 5 min."""
    for conn in connections:
        new_tokens = await refresh_job_token(refresh_token)
        if new_tokens:
            data["accessToken"] = new_tokens["access_token"]
            data["refreshToken"] = new_tokens["refresh_token"]
            # ... update DB
```

### Token Lifecycle dengan Auto-Refresh

```
Jam 0:     Import PAT → dapat jt-xxx + jrt-xxx
Jam 0-24:  Token fresh, langsung jalan
Jam 5:     Background refresh → token baru, timer reset
Jam 10:    Background refresh → token baru, timer reset
Jam 15:    Background refresh → token baru, timer reset
...
(selama server jalan, token tidak pernah expire)

Jam X:     Server mati
Jam X+48:  Refresh token expire → perlu re-import PAT
```

---

## Investigasi Mendalam: Qoder Token Types

### Device Token (`dt-xxx`)

- Didapat dari: Device flow (browser-based OAuth)
- Lifetime: ~30 hari
- Disimpan: `~/.qoder/.auth/user` (encrypted)
- Dipakai: qodercli, Veria IDE
- Bisa di-refresh: Ya, dengan device flow

### Job Token (`jt-xxx`)

- Didapat dari: PAT exchange (`/api/v1/jobToken/exchange`)
- Lifetime: ~24 jam
- Disimpan: Database (plaintext in JSON blob)
- Dipakai: 9router
- Bisa di-refresh: Ya, dengan refresh token

### Refresh Token (`jrt-xxx`)

- Didapat dari: Bersama job token
- Lifetime: ~48 jam
- Disimpan: Database (plaintext in JSON blob)
- Endpoint: `POST openapi.qoder.sh/api/v1/jobToken/refresh`
- Setiap refresh: dapat access token BARU + refresh token BARU

### Personal Access Token (`pt-xxx`)

- Didapat dari: qoder.com/account/integrations
- Lifetime: Tidak expire (selama tidak di-revoke)
- Dipakai: Untuk exchange ke job token
- Tidak bisa langsung dipakai untuk API calls

### Flow Lengkap

```
User dapat PAT (pt-xxx) dari qoder.com
        ↓
9router: POST /api/v1/jobToken/exchange {personal_token: "pt-xxx"}
        ↓
Response: {token: "jt-xxx", refreshToken: "jrt-xxx"}
        ↓
Simpan di DB, pakai untuk COSY-signed requests
        ↓
Setiap 5 menit: POST /api/v1/jobToken/refresh {refresh_token: "jrt-xxx"}
        ↓
Response: {token: "jt-yyy", refreshToken: "jrt-yyy"}  ← token baru
        ↓
Update DB, reset timer
```

---

## Ringkasan Perubahan

### Files Modified

| File | Perubahan |
|------|-----------|
| `backend/app/providers/qoder/constants.py` | Fix refresh endpoint URL |
| `backend/app/providers/qoder/auth.py` | Tambah `refresh_job_token()`, `try_refresh_connection()`, `refresh_all_qoder_connections()` |
| `backend/app/providers/qoder/handler.py` | `validate_connection()` calls `fetch_user_info()` |
| `backend/app/providers/qoder/cosy.py` | Refactor COSY signing |
| `backend/app/routers/providers/connections.py` | Tambah `invalidate_connection_cache()` setelah update |
| `backend/app/routers/models.py` | Reduce timeout 60s → 20s |
| `backend/app/routers/v1_proxy/chat.py` | Tambah auto-refresh on 401/403 + build failure |
| `backend/app/routers/v1_proxy/messages.py` | Tambah auto-refresh on 401/403 |
| `backend/app/routers/v1_proxy/responses.py` | Tambah auto-refresh on 401/403 |
| `backend/app/routers/v1_proxy/shared.py` | Tambah `_try_qoder_token_refresh()` helper |
| `backend/app/services/token_refresh.py` | Tambah Qoder refresh ke background task |

### Files Created

| File | Deskripsi |
|------|-----------|
| `backend/app/providers/DOCS/BUG-QODER-CACHE-STALE.md` | Dokumentasi bug cache stale |
| `backend/tests/test_qoder_cosy.py` | Unit tests COSY signing |

### Git Commit

```
736bfd2 fix(qoder): auto-refresh token + correct refresh endpoint
```

---

## Dokumen Terkait

- [QODER_PROVIDER_DOC.md](./QODER_PROVIDER_DOC.md) — Arsitektur lengkap Qoder provider
- [QODER_NEXT_SESSION_PROMPT.md](./QODER_NEXT_SESSION_PROMPT.md) — Context untuk AI session berikutnya
- [BUG-QODER-CACHE-STALE.md](./BUG-QODER-CACHE-STALE.md) — Detail bug cache stale

---

## Testing

### Test Auto-Refresh (Simulasi Token Expired)

```bash
# 1. Set fake expired token
docker exec 9router-postgres psql -U dev_9route -d db_9route -c "
UPDATE provider_connections 
SET data = jsonb_set(data::jsonb, '{accessToken}', '\"jt-FAKEEXPIRED\"')
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';
"

# 2. Test request (akan auto-refresh)
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"qd/qoder/qmodel_latest","messages":[{"role":"user","content":"hi"}]}'

# 3. Verify token updated
docker exec 9router-postgres psql -U dev_9route -d db_9route -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';
"
```

### Test Background Refresh

```bash
# 1. Record token
docker exec 9router-postgres psql -U dev_9route -d db_9route -t -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';"

# 2. Wait 6 minutes
sleep 360

# 3. Check token changed
docker exec 9router-postgres psql -U dev_9route -d db_9route -t -c "
SELECT data::jsonb->>'accessToken' FROM provider_connections 
WHERE id = '597689c2-a5d3-4883-a0e0-1abb069e6aa2';"
```

---

## Lessons Learned

1. **Jangan asumsi endpoint** — Qoder punya 2 base URL berbeda (openapi vs center), endpoint yang sama bisa return 403 di satu dan 200 di lainnya.

2. **Reverse-engineer dari sumber** — qodercli bundle (33MB) punya semua jawaban, tapi perlu grep teliti karena minified.

3. **Token types penting** — `dt-` vs `jt-` vs `jrt-` punya lifetime dan mekanisme refresh berbeda.

4. **Cache invalidation** — Selalu invalidate cache setelah update DB, terutama untuk proxy/router yang punya connection pool.

5. **Background task** — Untuk token expire, jangan hanya rely on-demand refresh. Background task memastikan token tetap hidup walau idle.
