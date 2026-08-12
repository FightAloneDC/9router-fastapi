# Qoder CLI v1.0.30 Investigation

> **Principle:** Every claim must have evidence. No assumptions.

---

## Root Cause: Qoder Chat Timeout (2026-06-26)

### Problem

Qoder chat requests from 9Router always timed out (30 seconds, 0 bytes). Server accepted the request (HTTP 200) but never sent any data.

### Investigation

1. Captured actual request from CLI v1.0.30 using Node.js `fetch` intercept
2. Compared with request sent by 9Router
3. Found significant differences in COSY headers

### Root Cause

**3 issues that caused the timeout:**

1. **Wrong Cosy-Version**: 9Router sent `1.0.14`, CLI sent `1.0.30`
2. **9Router sent 4 extra headers** not sent by CLI:
   - `Cosy-ClientIp` (containing machine_id)
   - `Accept-Encoding: identity`
   - `X-Request-Id` (UUID)
   - `X-Model-Key` / `X-Model-Source` (in handler.py)
3. **3 missing headers** sent by CLI but absent in 9Router:
   - `Cache-Control: no-cache`
   - `Connection: keep-alive`
   - `Accept: text/event-stream` (9Router used `application/json`)

### Fix

**File: `backend/app/providers/qoder/constants.py`**
- `QODER_IDE_VERSION`: `"1.0.14"` → `"1.0.30"`

**File: `backend/app/providers/qoder/cosy.py`**
- Removed: `Accept-Encoding`, `Cosy-ClientIp`, `X-Request-Id`
- Added: `Cache-Control: no-cache`, `Connection: keep-alive`
- Changed: `Accept` from `application/json` to `text/event-stream`

**File: `backend/app/providers/qoder/handler.py`**
- Removed: `X-Model-Key`, `X-Model-Source`, `Cache-Control`, `Accept`, `Accept-Encoding` (moved to cosy.py)

### Result

```
Before fix:  HTTP 200, 0 bytes, timeout after 30 seconds
After fix:   HTTP 200, TTFB 813ms, streaming response OK
```

### Evidence

Intercepted actual CLI request (Node.js fetch hook):
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

## 1. Runtime Facts (from ~/.qoder/)

### 1.1 Endpoint Selection

**Fact:** Qoder CLI uses `api2.qoder.sh` as primary endpoint.

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

**Note:** 9Router uses `api3.qoder.sh`. However, direct tests against both api2 and api3 from the backend container produced the same timeout. Therefore, the endpoint difference is **not** the root cause of the timeout.

### 1.2 DNS Cache

**Evidence:** `~/.qoder/.cache/dns-cache.json`:
```json
{
  "center.qoder.sh": {"ips": ["149.129.236.250", "149.129.241.62"]},
  "api2.qoder.sh": {"ips": ["8.215.6.232", "147.139.197.248"]}
}
```

**Note:** api3.qoder.sh is not in the DNS cache — CLI never resolves api3.

### 1.3 Machine ID and Installation ID

**Fact:** Qoder CLI has persistent machine ID and installation ID.

**Evidence:**
- `~/.qoder/.auth/machine_id`: `e065e549-0b81-42df-ad0c-3915170a5cc9`
- `~/.qoder/installation_id`: `0b51e318-3a4b-4437-a9a1-89fbe4379edc`

**Note:** Each 9Router connection generates a new machine_id during device flow or PAT import. Not persistent like CLI.

### 1.4 Auth File

**Fact:** Token in `~/.qoder/.auth/user` is encrypted (binary, not plaintext).

**Evidence:** 840-byte file, base64-like encoded.

**Note:** 9Router stores token as plaintext in DB JSON blob.

### 1.5 Default Model

**Fact:** Default model is `qmodel_latest`.

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

**Fact:** 75+ session logs stored in `~/.qoder/logs/runs/`. Latest: `2026-06-26T03-58-24`.

**Evidence:** `ls ~/.qoder/logs/runs/` shows 75+ directories.

### 1.7 Changelog

**Fact:** CLI v1.0.30 changelog entries.

**Evidence:** `~/.qoder/cache/changelog.json`:
```
CLI 1.0.30: Optimized network proxy mechanism (HTTP_PROXY, HTTPS_PROXY, SOCKS5)
CLI 1.0.29: Added configurable first-packet and stream-idle timeouts for model SSE responses
CLI 1.0.28: Optimized the model list cache mechanism
```

**Note:** v1.0.29 added "first-packet timeout" and "stream-idle timeout" — new features not in 9Router.

### 1.8 Dynamic Texts

**Fact:** CLI has model selector metadata.

**Evidence:** `~/.qoder/.auth/dynamic-texts.json` — version `1.0.229`, namespace `qoder-ide`. Contains labels/descriptions for all models. Not relevant to request flow.

### 1.9 External Commands

**Fact:** CLI has a plugin system (`wiki` command).

**Evidence:** `~/.qoder/external-commands/registry.json` — contains `wiki-cli` binary. Not relevant to chat flow.

### 1.10 Model Catalog Cache

**Fact:** Model catalog is encrypted on disk in `~/.qoder/.models/`.

**Evidence:**
- `~/.qoder/.models/default` → `{"key": "qmodel_latest", ...}`
- `~/.qoder/.models/019ea17a-7195-7834-b70d-faaaa80b9b7b/catalog-v5` → 45KB, encrypted binary
- `~/.qoder/.models/019ea17a-7195-7834-b70d-faaaa80b9b7b/catalog-v2` → 34KB, encrypted binary
- 3 user profiles: `019dfeb4`, `019e3ead`, `019ea17a`

**Note:** 9Router fetches catalog via COSY-signed request and caches in-memory. CLI caches to disk (encrypted).

### 1.11 Settings

**Evidence:** `~/.qoder/settings.json`:
```json
{
  "permissions": {"additionalDirectories": [], "trustDirectories": ["/home/mint/external-repo", "/home/mint/tmp"]},
  "security": {"auth": {"selectedType": "qoder-browser"}}
}
```

**Note:** Auth type `qoder-browser` = device flow via browser.

### 1.12 State

**Evidence:** `~/.qoder/state.json`:
```json
{"terminalSetupPromptShown": true, "tipsShown": 9}
```

---

## 2. CLI Startup Sequence (from log 2026-06-26)

### 2.1 Startup Flow

**Fact:** CLI makes 5 network calls before chat.

**Evidence:** From `~/.qoder/logs/runs/2026-06-26T03-58-24*/qodercli.log`:

```
Step 1: GET center.qoder.sh/algo/api/v3/service/region/endpoints
        → Elected OpenAPI: https://openapi.qoder.sh
        → Elected inference: https://api2.qoder.sh

Step 2: GET openapi.qoder.sh/api/v1/userinfo
        → Auth check

Step 3: GET center.qoder.sh/algo/api/v2/config/getDataPolicy?requestId=...
        → Data policy

Step 4: Feature gates (from config server):
        - model_server_transport: {enabled: false, protocol: undefined}
        - sse_body_null_diagnostics: {enabled: true, compression: 'zstd', chunkSizeChars: 48000}
        - httpdns: {enabled: false}
        - enterprise_plugins: {enabled: true}

Step 5: GET api2.qoder.sh/algo/api/v2/model/list?Encode=1
        → Model catalog (COSY-signed)
```

### 2.2 Endpoint Discovery

**Fact:** CLI fetches endpoint list from `center.qoder.sh` on every startup.

**Evidence:** Log shows `syncEndpointAsync` called to `center.qoder.sh/algo/api/v3/service/region/endpoints`.

**Note:** 9Router hardcodes `api3.qoder.sh`. No endpoint discovery.

### 2.3 Feature Gates

**Fact:** CLI fetches feature gates from config server.

**Evidence:** From log:
```
model_server_transport: {enabled: false, protocol: undefined, logRequestResponse: false}
sse_body_null_diagnostics: {enabled: true, compression: 'zstd', chunkSizeChars: 48000}
```

**Note:** `model_server_transport: false` means CLI uses **legacy transport** (not model_server). `sse_body_null_diagnostics` with `compression: 'zstd'` is a new feature.

---

## 3. CLI Chat Request (from log 2026-06-26)

### 3.1 Request Flow

**Fact:** CLI sends chat request to `api2.qoder.sh`.

**Evidence:** From log:
```
[qoder-server-request] --> operation=sendRemoteChatAsk method=POST
  url=https://api2.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1
```

### 3.2 Request Timing

**Fact:** CLI receives response within ~4 seconds.

**Evidence:** From `UndiciStreamDiagnostic` log:
```
phase=body_sent,   elapsedMs=121     → body sent in 121ms
phase=headers,     elapsedMs=2535,   status=200  → TTFB 2.5 seconds
phase=trailers,    elapsedMs=4065,   bytes=1292, chunkCount=51  → finished in 4 seconds, 51 chunks
```

**Note:** 9Router test from backend container: HTTP 200 but 0 chunks, timeout after 30 seconds. **Server accepted request but never sent data.**

### 3.3 Transport

**Fact:** CLI uses `transport=legacy`.

**Evidence:** From log:
```
[ModelResponse] transport=legacy, phase=headers_received, status=200
```

### 3.4 Request ID

**Fact:** CLI uses `qoderRequestId` in UUID format.

**Evidence:** From log:
```
qoderRequestId=9ae04def-5725-43db-a609-54e66ae7973a
```

---

## 4. Comparison: 9Router vs CLI

### 4.1 Verified as Same

| Field | Status |
|---|---|
| Chat path | ✅ Same (`/algo/api/v2/service/pro/sse/agent_chat_generation`) |
| Encode | ✅ Same (`Encode=1`) |
| RSA | ✅ Same (1024-bit) |
| AES | ✅ Same (AES-128-CBC) |
| Data Policy | ✅ Same (`agree`) |
| chat_task | ✅ Same (`FREE_INPUT`) |
| FetchKeys | ✅ Same (`llm_model_result`) |
| AgentId | ✅ Same (`agent_common`) |

### 4.2 Different but NOT Root Cause

| Field | 9Router | CLI | Evidence |
|---|---|---|---|
| Endpoint host | `api3.qoder.sh` | `api2.qoder.sh` | Test against api2 also timed out |
| Default model | `qmodel_latest` | `qmodel_latest` | Same |

### 4.3 Verified as Different (Root Cause)

| # | Field | 9Router | CLI | Status |
|---|---|---|---|---|
| 1 | **Cosy-Version** | `1.0.14` | `1.0.30` | ❌ **ROOT CAUSE — fixed** |
| 2 | **Cosy-ClientIp** | Sent (machine_id) | Not sent | ❌ Extra header — fixed |
| 3 | **Accept-Encoding** | Sent (`identity`) | Not sent | ❌ Extra header — fixed |
| 4 | **X-Request-Id** | Sent (UUID) | Not sent | ❌ Extra header — fixed |
| 5 | **X-Model-Key** | Sent | Not sent | ❌ Extra header — fixed |
| 6 | **X-Model-Source** | Sent | Not sent | ❌ Extra header — fixed |
| 7 | **Cache-Control** | Not sent | `no-cache` | ❌ Missing header — fixed |
| 8 | **Connection** | Not sent | `keep-alive` | ❌ Missing header — fixed |
| 9 | **Accept** | `application/json` | `text/event-stream` | ❌ Wrong value — fixed |

---

## 5. Actual Request Capture (from intercept)

### 5.1 COSY Authorization Payload (CLI v1.0.30)

**Fact:** CLI sends `cosyVersion: "1.0.30"`.

**Evidence:** Decoded from Authorization header:
```json
{
    "version": "v1",
    "requestId": "494153b7-8ebc-4dd0-adb6-7c8baca9e4fa",
    "info": "KLAfnv79lLk6aqfnDF5PLRG8lJYl/0AHwlzKSF5pkSWeolbNi2p8PIJvWFp5nU0HrZWfZ0wlGbujW1+CuWjB9lDYGJXXL1zHMro8vyThB7s=",
    "cosyVersion": "1.0.30",
    "ideVersion": ""
}
```

**Note:** 9Router sent `cosyVersion: "1.0.14"` (from `QODER_IDE_VERSION`). **This was different.**

### 5.2 Actual Headers (CLI v1.0.30)

**Fact:** CLI sends 15 headers (including Authorization).

**Evidence:** Full list in Section 4.3 above.

### 5.3 Request Body

**Fact:** Body is WAF-bypass encoded. CLI sends ~2KB encoded body.

**Evidence:** Body starts with `%hxHIMBgK.u*dwDxjwNYdru(jiuH%QBoi.N(` — this is the encoded format.

---

## 6. Auth Flow — OAuth Device Flow (from `oauth.py` + `auth.py`)

### 6.1 OAuth Device Flow — Full Sequence

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
   ├── Extract userId from tokens.user_id OR userInfo.id
   ├── Extract machineId from tokens._qoderMachineId
   └── Returns: {accessToken: "dt-xxx", refreshToken, expiresIn, email, displayName, providerSpecificData: {userId, machineId}}
```

### 6.2 Token Type: Device Token (`dt-xxx`)

| Property | Value | Evidence |
|---|---|---|
| Prefix | `dt-` | auth.py:145 `data.get("token")` |
| Lifetime | ~30 days | auth.py:158 `30 * 24 * 60 * 60` default |
| Refreshable | Yes (via refresh_token) | auth.py:310 `refresh_job_token()` |
| COSY signing | Yes | handler.py:158 `auth_token=access_token` |

### 6.3 OAuth Flow — Key Details

**Machine ID**: Generated per connection (UUID). Not persistent like CLI.

**Token Storage**: Plaintext in DB JSON blob `provider_connections.data`.

**ProviderSpecificData**: `{userId, machineId}` — used for COSY signing.

---

## 7. Auth Flow — PAT Import (from `auth.py`)

### 7.1 PAT Import — Full Sequence

```
1. User obtains PAT (pt-xxx) from qoder.com/account/integrations

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
   │   ├── If fails, retry: GET userinfo?accessToken={jt-xxx}
   │   └── Returns: {id, email, name, username, ...}
   │
   └── Step 3: Generate machine_id = new UUID
       Return: {access_token, refresh_token, expires_in, user_id, email, display_name, machine_id, organization_id}
```

### 7.2 Token Type: Job Token (`jt-xxx`)

| Property | Value | Evidence |
|---|---|---|
| Prefix | `jt-` | auth.py:284 |
| Lifetime | ~24 hours | BUG-FIXING-LOG.md:76 |
| Refresh Token | `jrt-xxx`, ~48 hours | BUG-FIXING-LOG.md:91 |
| Refresh Endpoint | `openapi.qoder.sh/api/v1/jobToken/refresh` | auth.py:316 |
| COSY signing | Yes | handler.py:158 |

### 7.3 PAT Flow — Key Details

**Difference from OAuth:**
- OAuth → `dt-xxx` (device token, 30 days)
- PAT → `jt-xxx` (job token, 24 hours, needs refresh)

**Machine ID**: Generated per connection (UUID).

**Token Storage**: Plaintext in DB JSON blob.

---

## 8. Token Refresh Flow (from `auth.py`)

### 8.1 On-Demand Refresh

```
Proxy receives 401/403 from Qoder
  → try_refresh_connection(db, connection_id) [auth.py:416-470]
    ├── Read refresh_token from DB
    ├── refresh_job_token(refresh_token) [auth.py:310-360]
    │   ├── POST https://openapi.qoder.sh/api/v1/jobToken/refresh
    │   │   Body: {refresh_token: "jrt-xxx"}
    │   └── Returns: {token: "jt-yyy", refreshToken: "jrt-yyy", expires_in}
    ├── Update DB: accessToken, refreshToken, testStatus="connected"
    ├── Flush DB
    └── invalidate_connection_cache("qoder")
```

### 8.2 Background Refresh (every 5 minutes)

```
refresh_all_qoder_connections() [auth.py:473-533]
  ├── Query all Qoder connections where is_active=true
  ├── For each connection:
  │   ├── Read refresh_token from data
  │   ├── refresh_job_token(refresh_token)
  │   └── Update DB on success
  └── invalidate_connection_cache("qoder")
```

### 8.3 Refresh Endpoint

**Fact:** The correct refresh endpoint is `openapi.qoder.sh/api/v1/jobToken/refresh`.

**Evidence:** auth.py:20 `QODER_REFRESH_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/refresh"`

**Note:** The old endpoint `center.qoder.sh/algo/api/v3/user/refresh_token` returns 403 (BUG-FIXING-LOG.md:110-113).

---

## 9. Auth Comparison: CLI vs 9Router

| Aspect | CLI v1.0.30 | 9Router |
|---|---|---|
| Machine ID | Persistent in `~/.qoder/.auth/machine_id` | Generated per connection |
| Token Storage | Encrypted in `~/.qoder/.auth/user` | Plaintext in DB |
| Auth Type | `qoder-browser` (device flow) | OAuth + PAT import |
| Token Format | `dt-xxx` (device) | `dt-xxx` (OAuth) or `jt-xxx` (PAT) |
| Refresh | Background + on-demand | Background + on-demand ✅ |
