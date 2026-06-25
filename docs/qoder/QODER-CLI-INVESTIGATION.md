# Qoder CLI v1.0.30 — Investigasi

> **Prinsip:** Setiap claim harus punya evidence. Tidak ada asumsi.

---

## Root Cause: Qoder Chat Timeout (2026-06-26)

### Masalah

Qoder chat request dari 9Router selalu timeout (30 detik, 0 bytes). Server accept request (HTTP 200) tapi tidak mengirim data.

### Investigasi

1. Capture actual request dari CLI v1.0.30 menggunakan Node.js `fetch` intercept
2. Compare dengan request yang dikirim 9Router
3. Ditemukan perbedaan signifikan di COSY headers

### Root Cause

**3 masalah yang menyebabkan timeout:**

1. **Cosy-Version salah**: 9Router mengirim `1.0.14`, CLI mengirim `1.0.30`
2. **9Router mengirim 4 header extra** yang tidak dikirim CLI:
   - `Cosy-ClientIp` (berisi machine_id)
   - `Accept-Encoding: identity`
   - `X-Request-Id` (UUID)
   - `X-Model-Key` / `X-Model-Source` (di handler.py)
3. **3 header hilang** yang dikirim CLI tapi tidak ada di 9Router:
   - `Cache-Control: no-cache`
   - `Connection: keep-alive`
   - `Accept: text/event-stream` (9Router pakai `application/json`)

### Fix

**File: `backend/app/providers/qoder/constants.py`**
- `QODER_IDE_VERSION`: `"1.0.14"` → `"1.0.30"`

**File: `backend/app/providers/qoder/cosy.py`**
- Hapus: `Accept-Encoding`, `Cosy-ClientIp`, `X-Request-Id`
- Tambah: `Cache-Control: no-cache`, `Connection: keep-alive`
- Ubah: `Accept` dari `application/json` ke `text/event-stream`

**File: `backend/app/providers/qoder/handler.py`**
- Hapus: `X-Model-Key`, `X-Model-Source`, `Cache-Control`, `Accept`, `Accept-Encoding` (sudah dipindah ke cosy.py)

### Hasil

```
Sebelum fix:  HTTP 200, 0 bytes, timeout 30 detik
Sesudah fix:  HTTP 200, TTFB 813ms, streaming response OK
```

### Evidence

Intercept actual CLI request (Node.js fetch hook):
```
Accept: text/event-stream
Authorization: Bearer COSY.{payload}.{sig}
Cache-Control: no-cache
Connection: keep-alive
Content-Type: application/json
Cosy-Business-Product: cli
Cosy-Business-Type: agent
Cosy-ClientType: 5
Cosy-Data-Policy: agree
Cosy-Date: 1782425825
Cosy-Key: ME+5DcidxAgDr8Jp6/Nl81SvPZC62hZOU+...
Cosy-MachineId: e065e549-0b81-42df-ad0c-3915170a5cc9
Cosy-MachineToken: e065e549-0b81-42df-ad0c-3915170a5cc9
Cosy-MachineType: 5
Cosy-Scene: assistant
Cosy-User: 019ea17a-7195-7834-b70d-faaaa80b9b7b
Cosy-Version: 1.0.30
Login-Version: v2
User-Agent: Qoder/1.0.30
```

---

## 1. Fakta Runtime (dari ~/.qoder/)

### 1.1 Endpoint Selection

**Fakta:** Qoder CLI menggunakan `api2.qoder.sh` sebagai primary endpoint.

**Evidence:** `~/.qoder/.cache/endpoint-cache.json`:
```json
{
  "version": 1,
  "entries": {
    "prod": {
      "endpoint": "https://api2.qoder.sh",
      "openapiEndpoints": ["https://openapi.qoder.sh"],
      "updatedAt": 1782421258741
    }
  }
}
```

**Catatan:** 9Router menggunakan `api3.qoder.sh`. Tapi test langsung ke api2 dan api3 dari backend container menghasilkan timeout yang sama. Jadi perbedaan endpoint **bukan** root cause timeout.

### 1.2 DNS Cache

**Evidence:** `~/.qoder/.cache/dns-cache.json`:
```json
{
  "center.qoder.sh": {"ips": ["149.129.236.250", "149.129.241.62"]},
  "api2.qoder.sh": {"ips": ["8.215.6.232", "147.139.197.248"]}
}
```

**Catatan:** api3.qoder.sh tidak ada di DNS cache — CLI tidak pernah resolve api3.

### 1.3 Machine ID & Installation ID

**Fakta:** Qoder CLI punya persistent machine ID dan installation ID.

**Evidence:**
- `~/.qoder/.auth/machine_id`: `e065e549-0b81-42df-ad0c-3915170a5cc9`
- `~/.qoder/installation_id`: `0b51e318-3a4b-4437-a9a1-89fbe4379edc`

**Catatan:** Setiap koneksi di 9Router punya machine_id yang di-generate baru saat device flow / PAT import. Tidak persisten seperti CLI.

### 1.4 Auth File

**Fakta:** Token di `~/.qoder/.auth/user` ter-encrypt (binary, bukan plaintext).

**Evidence:** File 840 bytes, base64-like encoded.

**Catatan:** 9Router simpan token plaintext di DB JSON blob.

### 1.5 Default Model

**Fakta:** Default model adalah `qmodel_latest`.

**Evidence:** `~/.qoder/.models/default`:
```json
{
  "key": "qmodel_latest",
  "uid": "019ea17a-7195-7834-b70d-faaaa80b9b7b",
  "scene": "assistant",
  "updatedAt": 1780998273341
}
```

### 1.6 Run Logs

**Fakta:** 75+ session logs tersimpan di `~/.qoder/logs/runs/`. Terakhir: `2026-06-26T03-58-24`.

**Evidence:** `ls ~/.qoder/logs/runs/` menunjukkan 75+ direktori.

### 1.7 Changelog

**Fakta:** CLI v1.0.30 changelog.

**Evidence:** `~/.qoder/cache/changelog.json`:
```
CLI 1.0.30: Optimized network proxy mechanism (HTTP_PROXY, HTTPS_PROXY, SOCKS5)
CLI 1.0.29: Added configurable first-packet and stream-idle timeouts for model SSE responses
CLI 1.0.28: Optimized the model list cache mechanism
```

**Catatan:** v1.0.29 menambahkan "first-packet timeout" dan "stream-idle timeout" — ini fitur baru yang 9Router tidak punya.

### 1.8 Dynamic Texts

**Fakta:** CLI punya model selector metadata.

**Evidence:** `~/.qoder/.auth/dynamic-texts.json` — version `1.0.229`, namespace `qoder-ide`. Berisi label/description untuk semua model. Tidak relevan dengan request flow.

### 1.9 External Commands

**Fakta:** CLI punya plugin system (`wiki` command).

**Evidence:** `~/.qoder/external-commands/registry.json` — berisi `wiki-cli` binary. Tidak relevan dengan chat flow.

### 1.10 Model Catalog Cache

**Fakta:** Model catalog ter-encrypt di `~/.qoder/.models/`.

**Evidence:**
- `~/.qoder/.models/default` → `{"key": "qmodel_latest", ...}`
- `~/.qoder/.models/019ea17a-7195-7834-b70d-faaaa80b9b7b/catalog-v5` → 45KB, encrypted binary
- `~/.qoder/.models/019ea17a-7195-7834-b70d-faaaa80b9b7b/catalog-v2` → 34KB, encrypted binary
- Ada 3 user profiles: `019dfeb4`, `019e3ead`, `019ea17a`

**Catatan:** 9Router fetch catalog via COSY-signed request dan cache in-memory. CLI cache ke disk (encrypted).

### 1.11 Settings

**Fakta:** CLI settings.

**Evidence:** `~/.qoder/settings.json`:
```json
{
  "permissions": {"additionalDirectories": [], "trustDirectories": ["/home/mint/external-repo", "/home/mint/tmp"]},
  "security": {"auth": {"selectedType": "qoder-browser"}}
}
```

**Catatan:** Auth type `qoder-browser` = device flow via browser.

### 1.12 State

**Evidence:** `~/.qoder/state.json`:
```json
{"terminalSetupPromptShown": true, "tipsShown": 9}
```

---

## 2. CLI Startup Sequence (dari log 2026-06-26)

### 2.1 Startup Flow

**Fakta:** CLI melakukan 5 network calls sebelum chat.

**Evidence:** Dari `~/.qoder/logs/runs/2026-06-26T03-58-24*/qodercli.log`:

```
Step 1: GET center.qoder.sh/algo/api/v3/service/region/endpoints
        → Elected OpenAPI: https://openapi.qoder.sh
        → Elected inference: https://api2.qoder.sh

Step 2: GET openapi.qoder.sh/api/v1/userinfo
        → Auth check

Step 3: GET center.qoder.sh/algo/api/v2/config/getDataPolicy?requestId=...
        → Data policy

Step 4: Feature gates (dari config server):
        - model_server_transport: {enabled: false, protocol: undefined}
        - sse_body_null_diagnostics: {enabled: true, compression: 'zstd', chunkSizeChars: 48000}
        - httpdns: {enabled: false}
        - enterprise_plugins: {enabled: true}

Step 5: GET api2.qoder.sh/algo/api/v2/model/list?Encode=1
        → Model catalog (COSY-signed)
```

### 2.2 Endpoint Discovery

**Fakta:** CLI fetch endpoint list dari `center.qoder.sh` setiap startup.

**Evidence:** Log menunjukkan `syncEndpointAsync` dipanggil ke `center.qoder.sh/algo/api/v3/service/region/endpoints`.

**Catatan:** 9Router hardcode `api3.qoder.sh`. Tidak ada endpoint discovery. **BELUM DIVERIFIKASI** apakah ini penyebab timeout.

### 2.3 Feature Gates

**Fakta:** CLI fetch feature gates dari config server.

**Evidence:** Dari log:
```
model_server_transport: {enabled: false, protocol: undefined, logRequestResponse: false}
sse_body_null_diagnostics: {enabled: true, compression: 'zstd', chunkSizeChars: 48000}
```

**Catatan:** `model_server_transport: false` artinya CLI pakai **legacy transport** (bukan model_server). `sse_body_null_diagnostics` dengan `compression: 'zstd'` — ini fitur baru.

---

## 3. CLI Chat Request (dari log 2026-06-26)

### 3.1 Request Flow

**Fakta:** CLI mengirim chat request ke `api2.qoder.sh`.

**Evidence:** Dari log:
```
[qoder-server-request] --> operation=sendRemoteChatAsk method=POST 
  url=https://api2.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1
```

### 3.2 Request Timing

**Fakta:** CLI mendapat response dalam ~4 detik.

**Evidence:** Dari `UndiciStreamDiagnostic` log:
```
phase=body_sent,   elapsedMs=121     → body terkirim dalam 121ms
phase=headers,     elapsedMs=2535,   status=200  → TTFB 2.5 detik
phase=trailers,    elapsedMs=4065,   bytes=1292, chunkCount=51  → selesai 4 detik, 51 chunks
```

**Catatan:** 9Router test dari backend container: 200 OK tapi 0 chunks, timeout 30 detik. **Server accept request tapi tidak kirim data.**

### 3.3 Transport

**Fakta:** CLI menggunakan `transport=legacy`.

**Evidence:** Dari log:
```
[ModelResponse] transport=legacy, phase=headers_received, status=200
```

### 3.4 Request ID

**Fakta:** CLI menggunakan `qoderRequestId` format UUID.

**Evidence:** Dari log:
```
qoderRequestId=9ae04def-5725-43db-a609-54e66ae7973a
```

---

## 4. Perbandingan: 9Router vs CLI

### 4.1 Sudah Diverifikasi Sama

| Field | Status |
|---|---|
| Chat path | ✅ Sama (`/algo/api/v2/service/pro/sse/agent_chat_generation`) |
| Encode | ✅ Sama (`Encode=1`) |
| RSA | ✅ Sama (1024-bit) |
| AES | ✅ Sama (AES-128-CBC) |
| Data Policy | ✅ Sama (`agree`) |
| chat_task | ✅ Sama (`FREE_INPUT`) |
| FetchKeys | ✅ Sama (`llm_model_result`) |
| AgentId | ✅ Sama (`agent_common`) |

### 4.2 Beda tapi BUKAN Root Cause

| Field | 9Router | CLI | Evidence |
|---|---|---|---|
| Endpoint host | `api3.qoder.sh` | `api2.qoder.sh` | Test ke api2 juga timeout |
| Default model | `qmodel_latest` | `qmodel_latest` | Sama |

### 4.3 BELUM Diverifikasi (Potential Root Cause)

| # | Field | 9Router | CLI | Perlu Verifikasi |
|---|---|---|---|---|
| 1 | **RSA public key** | Dari IDE v0.9 | Bundle v1.0.30 (ter-encrypt) | Capture actual COSY header dari CLI |
| 2 | **COSY headers lengkap** | 17 headers | ? | Capture actual headers dari CLI |
| 3 | **session_type** | `"qodercli"` | env-based | Capture actual request body |
| 4 | **Request body fields** | Ada 25+ fields | ? | Capture actual request body |
| 5 | **WAF encoding alphabet** | Dari qoder2api/QoderEncoding.java | ? | Capture actual encoded body |
| 6 | **Endpoint discovery** | Tidak ada | Fetch dari center.qoder.sh | Mungkin server reject tanpa ini |
| 7 | **Machine ID** | Generated per connection | Persistent file | Mungkin server track machine |
| 8 | **Version string** | `"1.0.0"` (business.version) | ? | Capture actual request |

---

## 7. Auth Flow — OAuth Device Flow (dari `oauth.py` + `auth.py`)

### 7.1 OAuth Device Flow — Full Sequence

```
1. initiate_device_flow() [auth.py:62-88]
   ├── Generate PKCE verifier (32 random bytes, base64url)
   ├── Generate S256 challenge (SHA256 of verifier, base64url)
   ├── Generate UUID nonce
   ├── Generate UUID machine_id ← NEW per connection
   └── Return: {verification_uri_complete, code_verifier, nonce, machine_id}
       URL: https://qoder.com/device/selectAccounts?challenge=...&nonce=...&machine_id=...

2. oauth.py: request_device_code() [oauth.py:38-52]
   ├── Calls initiate_device_flow()
   └── Returns device_code=nonce, codeVerifier=code_verifier, _qoderMachineId=machine_id

3. User opens URL in browser, authorizes

4. oauth.py: poll_token() [oauth.py:54-90]
   ├── Calls poll_device_token(nonce, verifier) [auth.py:91-170]
   │   ├── GET https://openapi.qoder.sh/api/v1/deviceToken/poll
   │   │   ?nonce=...&verifier=...&challenge_method=S256
   │   ├── Headers: {Accept: application/json, User-Agent: Go-http-client/2.0}
   │   ├── 202/404 = pending (keep polling)
   │   └── 200 = success: {token: "dt-xxx", expires_at, user_id, display_name, email}
   └── Returns: {access_token, refresh_token, expires_in, user_id, _qoderMachineId}

5. oauth.py: post_exchange() [oauth.py:92-102]
   ├── Calls fetch_user_info(access_token) [auth.py:173-230]
   │   ├── GET https://openapi.qoder.sh/api/v1/userinfo
   │   │   Headers: {Authorization: Bearer {dt-xxx}}
   │   └── Returns: {id, email, name, username, ...}
   └── Returns: {userInfo: {...}}

6. oauth.py: map_tokens() [oauth.py:116-141]
   ├── Extract userId dari tokens.user_id ATAU userInfo.id
   ├── Extract machineId dari tokens._qoderMachineId
   └── Returns: {accessToken: "dt-xxx", refreshToken, expiresIn, email, displayName, providerSpecificData: {userId, machineId}}
```

### 7.2 Token Type: Device Token (`dt-xxx`)

| Property | Value | Evidence |
|---|---|---|
| Prefix | `dt-` | auth.py:145 `data.get("token")` |
| Lifetime | ~30 hari | auth.py:158 `30 * 24 * 60 * 60` default |
| Refreshable | Ya (via refresh_token) | auth.py:310 `refresh_job_token()` |
| COSY signing | Ya | handler.py:158 `auth_token=access_token` |

### 7.3 OAuth Flow — Key Details

**Machine ID**: Generate baru per koneksi (UUID). Tidak persisten seperti CLI.

**Token Storage**: Plaintext di DB JSON blob `provider_connections.data`.

**ProviderSpecificData**: `{userId, machineId}` — ini yang dipakai COSY signing.

---

## 8. Auth Flow — PAT Import (dari `auth.py`)

### 8.1 PAT Import — Full Sequence

```
1. User dapat PAT (pt-xxx) dari qoder.com/account/integrations

2. import_pat(personal_token) [auth.py:363-413]
   ├── Step 1: exchange_personal_token(personal_token) [auth.py:233-307]
   │   ├── POST https://openapi.qoder.sh/api/v1/jobToken/exchange
   │   │   Body: {personal_token: "pt-xxx"}
   │   │   Headers: {Content-Type: application/json}
   │   ├── Parse response:
   │   │   access_token = data.token || data.device_token || data.access_token
   │   │   refresh_token = data.refreshToken || data.refresh_token
   │   │   expires_in = data.expires_in || data.expireTimeS
   │   │   refresh_token_expires_in = data.refresh_token_expires_in || data.refreshTokenExpireTimeS
   │   └── Returns: {access_token: "jt-xxx", refresh_token: "jrt-xxx", expires_in, refresh_token_expires_in}
   │
   ├── Step 2: fetch_user_info(access_token) [auth.py:173-230]
   │   ├── GET https://openapi.qoder.sh/api/v1/userinfo
   │   │   Headers: {Authorization: Bearer {jt-xxx}}
   │   ├── Jika gagal, coba: GET userinfo?accessToken={jt-xxx}
   │   └── Returns: {id, email, name, username, ...}
   │
   └── Step 3: Generate machine_id = UUID baru
       Return: {access_token, refresh_token, expires_in, user_id, email, display_name, machine_id, organization_id}
```

### 8.2 Token Type: Job Token (`jt-xxx`)

| Property | Value | Evidence |
|---|---|---|
| Prefix | `jt-` | auth.py:284 |
| Lifetime | ~24 jam | BUG-FIXING-LOG.md:76 |
| Refresh Token | `jrt-xxx`, ~48 jam | BUG-FIXING-LOG.md:91 |
| Refresh Endpoint | `openapi.qoder.sh/api/v1/jobToken/refresh` | auth.py:316 |
| COSY signing | Ya | handler.py:158 |

### 8.3 PAT Flow — Key Details

**Perbedaan dengan OAuth:**
- OAuth → `dt-xxx` (device token, 30 hari)
- PAT → `jt-xxx` (job token, 24 jam, perlu refresh)

**Machine ID**: Generate baru per koneksi (UUID).

**Token Storage**: Plaintext di DB JSON blob.

---

## 9. Token Refresh Flow (dari `auth.py`)

### 9.1 On-Demand Refresh

```
Proxy menerima 401/403 dari Qoder
  → try_refresh_connection(db, connection_id) [auth.py:416-470]
    ├── Baca refresh_token dari DB
    ├── refresh_job_token(refresh_token) [auth.py:310-360]
    │   ├── POST https://openapi.qoder.sh/api/v1/jobToken/refresh
    │   │   Body: {refresh_token: "jrt-xxx"}
    │   └── Returns: {token: "jt-yyy", refreshToken: "jrt-yyy", expires_in}
    ├── Update DB: accessToken, refreshToken, testStatus="connected"
    ├── Flush DB
    └── invalidate_connection_cache("qoder")
```

### 9.2 Background Refresh (setiap 5 menit)

```
refresh_all_qoder_connections() [auth.py:473-533]
  ├── Query semua Qoder connections yang is_active=true
  ├── Untuk setiap connection:
  │   ├── Baca refresh_token dari data
  │   ├── refresh_job_token(refresh_token)
  │   └── Update DB jika berhasil
  └── invalidate_connection_cache("qoder")
```

### 9.3 Refresh Endpoint

**Fakta:** Endpoint refresh yang benar adalah `openapi.qoder.sh/api/v1/jobToken/refresh`.

**Evidence:** auth.py:20 `QODER_REFRESH_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/refresh"`

**Catatan:** Endpoint lama `center.qoder.sh/algo/api/v3/user/refresh_token` return 403 (BUG-FIXING-LOG.md:110-113).

---

## 10. Perbedaan Auth: CLI vs 9Router

| Aspek | CLI v1.0.30 | 9Router |
|---|---|---|
| Machine ID | Persistent di `~/.qoder/.auth/machine_id` | Generate baru per koneksi |
| Token Storage | Encrypted di `~/.qoder/.auth/user` | Plaintext di DB |
| Auth Type | `qoder-browser` (device flow) | OAuth + PAT import |
| Token Format | `dt-xxx` (device) | `dt-xxx` (OAuth) atau `jt-xxx` (PAT) |
| Refresh | Background + on-demand | Background + on-demand ✅ |

---

## 11. Temuan: COSY Headers Perbedaan (dari intercept Section 5)

### 5.1 COSY Authorization Payload (CLI v1.0.30)

**Fakta:** CLI mengirim `cosyVersion: "1.0.30"`.

**Evidence:** Decode dari Authorization header:
```json
{
    "version": "v1",
    "requestId": "494153b7-8ebc-4dd0-adb6-7c8baca9e4fa",
    "info": "KLAfnv79lLk6aqfnDF5PLRG8lJYl/0AHwlzKSF5pkSWeolbNi2p8PIJvWFp5nU0HrZWfZ0wlGbujW1+CuWjB9lDYGJXXL1zHMro8vyThB7s=",
    "cosyVersion": "1.0.30",
    "ideVersion": ""
}
```

**Catatan:** 9Router mengirim `cosyVersion: "1.0.14"` (dari `QODER_IDE_VERSION`). **Ini beda.**

### 5.2 Actual Headers (CLI v1.0.30)

**Fakta:** CLI mengirim 15 headers (termasuk Authorization).

**Evidence:**
```
Accept: text/event-stream
Authorization: Bearer COSY.{payload}.{signature}
Cache-Control: no-cache
Connection: keep-alive
Content-Type: application/json
Cosy-Business-Product: cli
Cosy-Business-Type: agent
Cosy-ClientType: 5
Cosy-Data-Policy: agree
Cosy-Date: 1782425825
Cosy-Key: ME+5DcidxAgDr8Jp6/Nl81SvPZC62hZOU+...
Cosy-MachineId: e065e549-0b81-42df-ad0c-3915170a5cc9
Cosy-MachineToken: e065e549-0b81-42df-ad0c-3915170a5cc9
Cosy-MachineType: 5
Cosy-Scene: assistant
Cosy-User: 019ea17a-7195-7834-b70d-faaaa80b9b7b
Cosy-Version: 1.0.30
Login-Version: v2
traceparent: 00-9770df7174b0a8089beb6af012fb6dfb-5b280b4343450389-01
```

### 5.3 Perbandingan Headers (KRITIS)

| Header | CLI v1.0.30 | 9Router | Status |
|---|---|---|---|
| **Cosy-Version** | **`1.0.30`** | **`1.0.14`** | ❌ **BEDA — root cause?** |
| Cosy-MachineId | Persistent (file) | Generated per conn | ⚠️ Beda |
| Cosy-MachineToken | Persistent (file) | Generated per conn | ⚠️ Beda |
| Cosy-ClientIp | **TIDAK ADA** | machine_id | ❌ 9Router kirim extra |
| Cosy-MachineOs | **TIDAK ADA** | `x86_64_windows` | ❌ 9Router kirim extra |
| Cosy-BodyHash | **TIDAK ADA** | MD5(body) | ❌ 9Router kirim extra |
| Cosy-BodyLength | **TIDAK ADA** | len(body) | ❌ 9Router kirim extra |
| Cosy-SigPath | **TIDAK ADA** | URL path | ❌ 9Router kirim extra |
| X-Model-Key | **TIDAK ADA** | model key | ❌ 9Router kirim extra |
| X-Model-Source | **TIDAK ADA** | source | ❌ 9Router kirim extra |
| X-Request-Id | **TIDAK ADA** | UUID | ❌ 9Router kirim extra |
| Accept-Encoding | **TIDAK ADA** | `identity` | ❌ 9Router kirim extra |
| Connection | `keep-alive` | TIDAK ADA | ⚠️ CLI punya, 9Router tidak |
| traceparent | Ada (OTel) | TIDAK ADA | Normal (CLI telemetry) |

**KESIMPULAN:** 9Router mengirim **10 header extra** yang TIDAK dikirim CLI. Dan `Cosy-Version` beda (`1.0.14` vs `1.0.30`).

### 5.4 Request Body

**Fakta:** Body ter-encode (WAF bypass). CLI mengirim ~2KB encoded body.

**Evidence:** Body dimulai dengan `%hxHIMBgK.u*dwDxjwNYdru(jiuH%QBoi.N(` — ini encoded format.

---

## 6. Langkah Selanjutnya

Perlu **capture actual network traffic** dari Qoder CLI untuk membandingkan dengan 9Router.
Pilihan: NODE_DEBUG, strace, tcpdump, atau mitmproxy.
