# Qoder Provider — Technical Documentation

> Dokumen ini berisi hasil investigasi tentang provider Qoder, termasuk arsitektur, autentikasi, COSY signing, dan troubleshooting.

---

## Daftar Isi

1. [Arsitektur Overview](#arsitektur-overview)
2. [File Structure](#file-structure)
3. [Authentication Methods](#authentication-methods)
4. [Token Lifecycle](#token-lifecycle)
5. [COSY Signing Mechanism](#cosy-signing-mechanism)
6. [API Endpoints](#api-endpoints)
7. [Model Catalog](#model-catalog)
8. [Error Handling](#error-handling)
9. [Known Issues & Solutions](#known-issues--solutions)
10. [Troubleshooting](#troubleshooting)

---

## Arsitektur Overview

Qoder adalah provider AI yang menggunakan **COSY signing** (RSA + AES + MD5) untuk autentikasi request. Berbeda dengan provider lain yang menggunakan Bearer token sederhana, Qoder memerlukan:

- **COSY-signed headers** untuk setiap request
- **WAF-bypass body encoding** untuk menghindari pattern matching oleh Alibaba Cloud WAF
- **Custom request/response transformation** (OpenAI format → Qoder format)

### Alur Request

```
Client (OpenAI format)
    ↓
9Router Proxy
    ↓
QoderHandler.build_request_body()
    ├── Transform OpenAI → Qoder format
    ├── WAF-bypass encode (base64 + rearrange + substitute)
    └── COSY sign (RSA encrypt AES key + AES encrypt user info + MD5 signature)
    ↓
Qoder API (api3.qoder.sh)
    ↓
QoderHandler.unwrap_response()
    └── Unwrap Qoder envelope → OpenAI format
    ↓
Client (OpenAI format)
```

---

## File Structure

```
backend/app/providers/qoder/
├── __init__.py      # Package exports
├── config.py        # Provider config (PROVIDER_NAME, ALIAS, BASE_URL)
├── handler.py       # Handler methods (build_url, build_headers, etc.)
├── auth.py          # OAuth device flow + PAT import
├── constants.py     # URLs, COSY constants, RSA public key
├── cosy.py          # COSY signing implementation (RSA + AES + MD5)
├── encoding.py      # WAF-bypass body encoding
├── models.py        # Model catalog fetching + caching
└── transform.py     # Request/response transformation
```

### Tanggung Jawab Setiap File

| File | Tanggung Jawab |
|------|---------------|
| `config.py` | Konfigurasi statis provider (nama, alias, base URL, format) |
| `handler.py` | Entry point untuk proxy dispatch (build_upstream_url, build_headers, build_request_body, unwrap_response, fetch_models) |
| `auth.py` | Autentikasi: device flow (PKCE), PAT import, fetch user info |
| `constants.py` | Konstanta: URL endpoints, COSY header values, RSA public key, custom alphabet |
| `cosy.py` | Implementasi COSY signing: RSA encrypt, AES-CBC encrypt, MD5 signature |
| `encoding.py` | WAF-bypass encoding: base64 → rearrange → character substitution |
| `models.py` | Fetch model catalog dari Qoder API, caching 1 jam |
| `transform.py` | Transformasi request (OpenAI → Qoder) dan response (Qoder → OpenAI) |

---

## Authentication Methods

Qoder mendukung **2 metode** autentikasi:

### 1. OAuth Device Flow

```
User klik "Login with Qoder"
    ↓
Generate PKCE pair (verifier + challenge) + nonce + machine_id
    ↓
Buka browser: https://qoder.com/device/selectAccounts?challenge=...&nonce=...
    ↓
Poll https://openapi.qoder.sh/api/v1/deviceToken/poll
    ↓
User authorize di browser
    ↓
Server return dt-xxx access token
    ↓
Fetch user info
    ↓
Simpan ke DB (accessToken, refreshToken, userId, machineId, dll)
```

**Token Format:**
- Access Token: `dt-xxx` (device token)
- Refresh Token: `jrt-xxx` (JWT refresh token)

### 2. PAT Import (Personal Access Token)

```
User dapat PAT (pt-xxx) dari qoder.com/account/integrations
    ↓
Exchange PAT → regular token via /api/v1/jobToken/exchange
    ↓
Fetch user info dengan regular token
    ↓
Simpan ke DB
```

**Token Format:**
- PAT: `pt-xxx` (personal access token)
- Regular Token: `jt-xxx` (job token) — digunakan untuk COSY signing

---

## Token Lifecycle

### Token Lifetime

| Token Type | Lifetime | Catatan |
|------------|----------|---------|
| Access Token (dt-xxx) | ~30 days | Dari device flow |
| Regular Token (jt-xxx) | ~30 days | Dari PAT exchange |
| Refresh Token (jrt-xxx) | ~30 days | Untuk refresh access token |

### Token Expiry Behavior

**Penting:** Token Qoder memiliki behavior berbeda tergantung endpoint:

| Endpoint | Auth Required | Behavior saat Token Expired |
|----------|---------------|----------------------------|
| `/algo/api/v2/model/list` | Ya (COSY signed) | 403 "Login expired" |
| `/algo/api/v2/service/pro/sse/agent_chat_generation` | Ya (COSY signed) | 500 Internal Server Error |
| `/api/v1/userinfo` | Ya (Bearer) | 401/403 |

**Catatan Penting:**
- Model list endpoint **memerlukan autentikasi** — jika userId valid tapi token expired, return 403
- Jika userId tidak dikenal, API bisa return 200 dengan default model list (tanpa autentikasi)
- Refresh token endpoint (`/algo/api/v3/user/refresh_token`) **tidak berfungsi** untuk device flow — selalu return 403

### Token Refresh

```python
# Refresh token URL
QODER_REFRESH_TOKEN_URL = "https://center.qoder.sh/algo/api/v3/user/refresh_token"

# Status: TIDAK BERFUNGSI untuk device flow
# Response: 403 "Request discarded"
```

**Kesimpulan:** Ketika token expired, user **harus re-authenticate** (login ulang) melalui device flow atau PAT import.

---

## COSY Signing Mechanism

COSY (COmposite Signature sYstem) adalah mekanisme signing yang digunakan Qoder untuk mengotentikasi request. Setiap request ke inference endpoint harus di-sign dengan COSY.

### Komponen COSY

1. **RSA-2048** — Mengenkripsi AES key
2. **AES-128-CBC** — Mengenkripsi user info
3. **MD5** — Membuat signature dari payload

### Proses COSY Signing

```
1. Generate AES key (16 bytes random)
    ↓
2. Encrypt user info dengan AES-128-CBC
   - Plaintext: {"uid": "...", "security_oauth_token": "...", "name": "...", "email": "..."}
   - Key: AES key
   - IV: first 16 bytes of AES key
   - Output: base64 encoded ciphertext → "info"
    ↓
3. Encrypt AES key dengan RSA-2048
   - Public key: hardcoded di constants.py
   - Padding: PKCS1v15
   - Output: base64 encoded encrypted key → "cosyKey"
    ↓
4. Build payload JSON
   {
     "version": "v1",
     "requestId": "<uuid>",
     "info": "<encrypted user info>",
     "cosyVersion": "1.0.0",
     "ideVersion": ""
   }
   → base64 encode → "payloadB64"
    ↓
5. Compute signature
   sigPath = URL path tanpa /algo prefix
   sigInput = "{payloadB64}\n{cosyKey}\n{timestamp}\n{body}\n{sigPath}"
   signature = MD5(sigInput)
    ↓
6. Build Authorization header
   "Bearer COSY.{payloadB64}.{signature}"
    ↓
7. Build COSY headers (17+ headers)
   - Cosy-Key: encrypted AES key
   - Cosy-User: user ID
   - Cosy-Date: timestamp
   - Cosy-Machineid: machine UUID
   - Cosy-Bodyhash: MD5 of request body
   - Cosy-Bodylength: length of request body
   - Cosy-Sigpath: URL path tanpa /algo
   - ... (14+ headers lainnya)
```

### COSY Headers Lengkap

```python
{
    "Authorization": "Bearer COSY.<payload>.<signature>",
    "Cosy-Key": "<RSA-encrypted AES key>",
    "Cosy-User": "<user_id>",
    "Cosy-Date": "<unix_timestamp>",
    "Cosy-Version": "1.0.0",
    "Cosy-Machineid": "<machine_uuid>",
    "Cosy-Machinetoken": "<machine_uuid>",
    "Cosy-Machinetype": "5",
    "Cosy-Machineos": "x86_64_windows",
    "Cosy-Clienttype": "5",
    "Cosy-Clientip": "127.0.0.1",
    "Cosy-Bodyhash": "<MD5 of body>",
    "Cosy-Bodylength": "<body length>",
    "Cosy-Sigpath": "<URL path without /algo>",
    "Cosy-Data-Policy": "disagree",
    "Cosy-Organization-Id": "",
    "Cosy-Organization-Tags": "",
    "Login-Version": "v2",
    "X-Request-Id": "<uuid>",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "identity",
    "User-Agent": "Qoder/1.0.0",
}
```

---

## API Endpoints

### Base URLs

| Host | Purpose |
|------|---------|
| `openapi.qoder.sh` | Auth endpoints (device flow, user info, quota) |
| `center.qoder.sh` | Token refresh |
| `api3.qoder.sh` | Inference endpoints (chat, model list) |

### Auth Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `openapi.qoder.sh/api/v1/deviceToken/poll` | GET | Poll device token |
| `openapi.qoder.sh/api/v1/userinfo` | GET | Fetch user info |
| `openapi.qoder.sh/api/v1/jobToken/exchange` | POST | Exchange PAT → regular token |
| `center.qoder.sh/algo/api/v3/user/refresh_token` | POST | Refresh token (TIDAK BERFUNGSI) |

### Inference Endpoints (COSY-signed)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `api3.qoder.sh/algo/api/v2/model/list` | GET | Fetch model catalog |
| `api3.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1` | POST | Chat completion (SSE) |

### Chat Request Flow

```
1. Client → POST /v1/chat/completions (OpenAI format)
2. 9Router → resolve model → select connection
3. QoderHandler.build_request_body()
   a. Transform OpenAI → Qoder format
   b. WAF-bypass encode body
   c. COSY sign with encoded body
4. 9Router → POST to Qoder API (SSE)
5. QoderHandler.unwrap_response()
   a. Parse SSE chunks
   b. Unwrap Qoder envelope
   c. Aggregate content
6. 9Router → return to client (OpenAI format)
```

---

## Model Catalog

### Available Models (per Juni 2026)

| Model ID | Display Name | Context Length | Price Factor | Notes |
|----------|--------------|----------------|--------------|-------|
| `auto` | Auto | 180K | 1.0 | Default, VL support |
| `ultimate` | Ultimate | 180K | 1.6 | Reasoning support |
| `performance` | Performance | 272K | 1.1 | Higher context |
| `efficient` | Efficient | 180K | 0.3 | Cost-efficient |
| `qmodel_latest` | Qwen3.7-Max | 180K | 0.2 | **FREE**, default |
| `qmodel` | Qwen3.7-Plus | 180K | 0.1 | |
| `dmodel` | DeepSeek-V4-Pro | 180K | 0.5 | Reasoning support |
| `dfmodel` | DeepSeek-V4-Flash | 180K | 0.1 | Reasoning, fast |
| `gm51model` | GLM-5.1 | 180K | 0.6 | Reasoning support |
| `kmodel` | Kimi-K2.6 | 256K | 0.3 | Higher context |
| `mmodel` | MiniMax-M3 | 180K | 0.2 | |

### Model Features

- **VL (Vision-Language)**: Semua model mendukung input gambar
- **Reasoning**: Model dengan reasoning support (ultimate, dmodel, dfmodel, gm51model)
- **Context Config**: Beberapa model mendukung konfigurasi context (200K, 400K, 1M)
- **Thinking Config**: Model reasoning mendukung thinking intensity (low, medium, high, xhigh, max)

### Model Caching

```python
# Cache TTL: 1 jam
CACHE_TTL_MS = 60 * 60 * 1000

# Cache key: hash(userId + accessToken)
# Cache location: in-memory (_catalog_cache dict)
```

---

## Error Handling

### Error Responses

| HTTP Status | Message | Penyebab | Solusi |
|-------------|---------|----------|--------|
| 403 | "Login expired" | Token expired | Re-authenticate (login ulang) |
| 403 | "Request discarded" | Refresh token invalid | Re-authenticate |
| 500 | "Internal Server Error" | Token expired (chat endpoint) | Re-authenticate |
| 401 | "Unauthorized" | Token invalid | Re-authenticate |

### Error Propagation

```
Qoder API (403 "Login expired")
    ↓
fetch_qoder_catalog() → raise httpx.HTTPStatusError
    ↓
resolve_qoder_models() → propagate error
    ↓
QoderHandler.fetch_models() → propagate error
    ↓
_fetch_builtin_models() → catch httpx.HTTPStatusError
    ↓
HTTPException(status_code=403, detail="Login expired")
    ↓
Frontend → show notification "Login expired"
```

---

## Known Issues & Solutions

### Issue 1: Token Expired

**Symptom:**
- Fetch models return 403 "Login expired"
- Chat requests return 500 "Internal Server Error"

**Root Cause:**
- Token lifetime ~30 hari
- Refresh token endpoint tidak berfungsi untuk device flow
- Tidak ada mekanisme auto-refresh

**Solution:**
- User harus **re-authenticate** (login ulang) melalui:
  1. Device flow: klik "Login with Qoder"
  2. PAT import: paste PAT baru dari qoder.com/account/integrations

**Prevention:**
- Monitor token expiry di connection data (`expiresAt` field)
- Tampilkan warning di UI jika token akan expired dalam 7 hari

### Issue 2: Empty Models List

**Symptom:**
- Fetch models return empty list `[]`
- Tidak ada error message

**Root Cause:**
- Token expired, tapi error tidak di-propagate dengan benar
- Handler mengembalikan empty list tanpa error

**Solution:**
- Sudah diperbaiki: error sekarang di-propagate ke frontend
- Frontend menampilkan notification "Login expired"

### Issue 3: COSY Signing Failure

**Symptom:**
- Request ke Qoder API gagal dengan error signing

**Root Cause:**
- userId atau accessToken kosong
- Machine ID tidak valid

**Solution:**
- Pastikan connection data memiliki:
  - `accessToken`: token yang valid
  - `userId`: Qoder user ID
  - `machineId`: machine UUID

---

## Troubleshooting

### Cek Token Validity

```bash
# Via API
curl -X GET "https://openapi.qoder.sh/api/v1/userinfo" \
  -H "Authorization: Bearer <access_token>"

# Response 200 = token valid
# Response 401/403 = token expired/invalid
```

### Cek Model List

```bash
# Via 9Router API
curl -X GET "http://localhost:9000/providers/<conn_id>/models" \
  -H "Authorization: Bearer <9router_token>"

# Response: {"models": [...]} = success
# Response: {"detail": "Login expired"} = token expired
```

### Debug COSY Signing

```python
from app.providers.qoder.cosy import build_cosy_headers
from app.providers.qoder.constants import QODER_CHAT_URL_ENCODED

headers = build_cosy_headers(
    body=b"",
    request_url=QODER_CHAT_URL_ENCODED,
    user_id="<user_id>",
    auth_token="<access_token>",
    name="<display_name>",
    email="<email>",
    machine_id="<machine_id>",
)

print(headers["Authorization"])
# Expected: "Bearer COSY.<payload>.<signature>"
```

### Check Connection Data

```python
from app.database import async_session
from app.models.provider import ProviderConnection
from sqlalchemy import select
import json

async def check_connection(conn_id: str):
    async with async_session() as db:
        result = await db.execute(
            select(ProviderConnection).where(ProviderConnection.id == conn_id)
        )
        conn = result.scalar_one_or_none()
        if conn:
            data = json.loads(conn.data) if conn.data else {}
            print("Token:", data.get("accessToken", "NOT FOUND")[:20] + "...")
            print("User ID:", data.get("userId", "NOT FOUND"))
            print("Machine ID:", data.get("machineId", "NOT FOUND"))
            print("Expires At:", data.get("expiresAt", "NOT FOUND"))
```

---

## Referensi

- **COSY Signing**: Implementasi di `cosy.py`, diport dari Node.js (`src/lib/qoder/cosy.js`)
- **WAF-bypass Encoding**: Implementasi di `encoding.py`, diport dari Java (`qoder2api/QoderEncoding.java`)
- **Transform**: Implementasi di `transform.py`, diport dari Node.js
- **Auth**: Implementasi di `auth.py`, diport dari Node.js

---

## Changelog

| Tanggal | Perubahan |
|---------|-----------|
| 2026-06-07 | Dokumentasi awal |
| 2026-06-07 | Fix error handling: propagate "Login expired" ke frontend |
| 2026-06-07 | Consolidasi dari `services/qoder/` ke `providers/qoder/` |
| 2026-06-07 | Integrasi dengan handler system (proxy dispatch) |
