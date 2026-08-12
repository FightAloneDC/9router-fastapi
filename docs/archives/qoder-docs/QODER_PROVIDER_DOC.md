# Qoder Provider — Flow & Architecture Documentation

> This document is a comprehensive reference for `backend/app/providers/qoder/`.
> Use as reference to avoid re-scanning in other sessions.

---

## 1. Overview

Qoder is an AI provider that **does not use OpenAI-compatible format**. It has its own protocol:

- **COSY Signing** — hybrid RSA + AES + MD5 authentication (not a standard Bearer token)
- **WAF-bypass encoding** — request body is encoded to avoid Alibaba Cloud WAF pattern-matching
- **Custom envelope response** — response is wrapped in an envelope, not direct OpenAI JSON
- **OAuth device flow** — authentication uses a custom device token flow (not standard OAuth2)
- **PAT import** — alternative: import Personal Access Token (pt-xxx) which is exchanged for a regular token

Provider ID: `qoder`, Alias: `qd`, Category: Special (complex auth).

---

## 2. File Structure & Responsibilities

```
backend/app/providers/qoder/
├── __init__.py      # Public API exports (barrel file)
├── config.py        # QoderConfig + QoderMetadata (static identity & UI metadata)
├── constants.py     # URLs, model map, RSA key, encoding alphabet
├── auth.py          # Device flow + PAT import authentication
├── oauth.py         # QoderOAuthHandler (DeviceCodeHandler subclass)
├── handler.py       # QoderHandler (BaseProviderHandler subclass) — core proxy handler
├── models.py        # Model catalog fetching + caching (COSY-signed)
├── transform.py     # OpenAI ↔ Qoder request/response transformation
├── encoding.py      # WAF-bypass body encoding
└── cosy.py          # COSY signing (RSA+AES+MD5)
```

---

## 3. Authentication Flows

### 3a. OAuth Device Flow (primary)

```
User → Frontend
  │
  ├─ 1. initiate_device_flow()
  │     - Generate PKCE verifier + S256 challenge (32 random bytes)
  │     - Generate UUID nonce + machine_id
  │     - Build URL: https://qoder.com/device/selectAccounts?challenge=...&nonce=...
  │     - Return: { verification_uri_complete, code_verifier, nonce, machine_id }
  │
  ├─ 2. User opens URL in browser, authorizes
  │
  └─ 3. poll_device_token(nonce, code_verifier)
        - GET https://openapi.qoder.sh/api/v1/deviceToken/poll?nonce=...&verifier=...
        - 202/404 = pending (keep polling)
        - 200 = success: returns { token, expires_at, user_id, email, display_name }
        - Token format: dt-xxx
        - Default expiry: 30 days
```

### 3b. PAT Import (alternative)

```
User provides PAT (pt-xxx) from qoder.com/account/integrations
  │
  ├─ 1. exchange_personal_token(pat)
  │     - POST https://openapi.qoder.sh/api/v1/jobToken/exchange
  │     - Body: { personal_token: "pt-xxx" }
  │     - Returns: regular token (for COSY signing), refresh_token, expires_in
  │
  ├─ 2. fetch_user_info(access_token)
  │     - GET https://openapi.qoder.sh/api/v1/userinfo
  │     - Auth: Bearer {token} (fallback: ?accessToken= query param)
  │     - Returns: { id, email, name, ... }
  │
  └─ 3. import_pat() orchestrates
        - Generates UUID machine_id
        - Returns connection data: { access_token, refresh_token, user_id, email, display_name, machine_id }
```

### 3c. Token Refresh

- Endpoint: POST https://center.qoder.sh/algo/api/v3/user/refresh_token
- In practice: **no-op** — upstream returns 403 for this flow
- Token expires ~30 days, user must re-login

---

## 4. COSY Signing System

Every request to the inference endpoint **must** be signed with COSY. This is the most complex part.

### 4a. Build COSY Headers (`build_cosy_headers()`)

```
Input: body_bytes, request_url, user_id, auth_token, name, email, machine_id

Step 1: Encrypt user info
  - Generate AES-128 key (16 chars from UUID)
  - AES-CBC encrypt: { uid, security_oauth_token, name, aid, email }
  - RSA-PKCS1v15 encrypt: AES key → "Cosy-Key"

Step 2: Build payload
  - payload_json = { version: "v1", requestId, info: AES_encrypted, cosyVersion, ideVersion }
  - payload_b64 = base64(payload_json)

Step 3: Compute signature
  - sig_path = URL path without /algo prefix
  - sig_input = "{payload_b64}\n{cosy_key}\n{timestamp}\n{body}\n{sig_path}"
  - sig = MD5(sig_input)
  - Authorization = "Bearer COSY.{payload_b64}.{sig}"

Step 4: Return 17+ headers
  - Authorization: Bearer COSY.{payloadB64}.{sig}
  - Cosy-Key: RSA-encrypted AES key (base64)
  - Cosy-User: user_id
  - Cosy-Date: unix timestamp
  - Cosy-Version, Cosy-Machineid, Cosy-Machinetoken, Cosy-Machinetype,
    Cosy-Machineos, Cosy-Clienttype, Cosy-Clientip, Cosy-Bodyhash,
    Cosy-Bodylength, Cosy-Sigpath, Cosy-Data-Policy, Cosy-Organization-Id,
    Cosy-Organization-Tags, Login-Version, X-Request-Id
  - Content-Type, Accept, Accept-Encoding, User-Agent
```

### 4b. Key Constants

| Constant | Value |
|----------|-------|
| QODER_IDE_VERSION | "1.0.0" |
| QODER_CLIENT_TYPE | "5" |
| QODER_MACHINE_OS | "x86_64_windows" |
| QODER_MACHINE_TYPE | "5" |
| QODER_DATA_POLICY | "disagree" |
| QODER_LOGIN_VERSION | "v2" |

RSA public key: 1024-bit, extracted from Qoder IDE v0.9.

---

## 5. WAF-Bypass Encoding (`encoding.py`)

Request body is encoded before sending to avoid Alibaba Cloud WAF:

```
Algorithm:
  1. base64-encode plaintext bytes (standard alphabet)
  2. Rearrange: split into 3 parts, reorder as [tail][mid][head]
  3. Substitute: each character is mapped from standard alphabet to custom alphabet

Standard: ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
Custom:   _doRTgHZBKcGVjlvpC,@aFSx#DPuNJme&i*MzLOEn)sUrthbf%Y^w.(kIQyXqWA!
'=' → '$'

URL endpoint is appended with &Encode=1 for the server to know to decode.
```

---

## 6. Request Transformation (`transform.py`)

### 6a. OpenAI → Qoder (`build_qoder_request_body()`)

Input: OpenAI-format `{ model, messages, tools, max_tokens, ... }`

Output: Qoder-format body with structure:
```json
{
  "request_id": "uuid",
  "request_set_id": "stable_hash",
  "chat_record_id": "stable_hash",
  "session_id": "stable_hash",
  "stream": true,
  "chat_task": "FREE_INPUT",
  "is_reply": true,
  "is_retry": false,
  "source": 1,
  "version": "3",
  "session_type": "qodercli",
  "agent_id": "agent_common",
  "task_id": "common",
  "system": "extracted system prompt",
  "messages": "non-system messages",
  "tools": [],
  "parameters": { "max_tokens": 32768 },
  "chat_context": {
    "chatPrompt": "",
    "extra": {
      "context": [],
      "modelConfig": { "key": "auto", "is_reasoning": false },
      "originalContent": "last user text"
    },
    "text": "last user text"
  },
  "model_config": "full model config from catalog",
  "business": {
    "product": "cli",
    "version": "1.0.0",
    "type": "agent",
    "stage": "start",
    "id": "uuid",
    "name": "truncated last user text (30 chars)",
    "begin_at": "timestamp_ms"
  }
}
```

Key transformations:
- `messages`: system messages are extracted to the `system` field, the rest in `messages`
- `tools`: preserved from the original request
- `max_tokens`: from request body or default 32768
- `session_id`: stable hash from user_id + model_key
- `chat_record_id`: stable hash from model + messages + tools + max_tokens
- `model_config`: full config from catalog (required, fetch from API if missing)

### 6b. Qoder → OpenAI (Response Unwrapping)

Qoder sends response in 3 formats:

**Streaming (SSE):**
```
data: {"headers":{...},"body":"..."}     ← new format
data: {"statusCodeValue":200,"body":"..."} ← old format
data: {"choices":[...],...}              ← direct OpenAI
data: [DONE]
```

Unwrapping: extract `body` field, sanitize newlines, forward as standard SSE.

**Non-streaming:**
- Can be SSE (Qoder always uses SSE even for non-stream) → unwrap + aggregate chunks
- Can be plain JSON envelope → unwrap `body` field
- Can be direct OpenAI format → pass through

---

## 7. Model Catalog (`models.py`)

### 7a. Fetching

```
fetch_qoder_catalog(credentials)
  → GET https://api3.qoder.sh/algo/api/v2/model/list (COSY-signed)
  → Response: { chat: [ { key, display_name, max_input_tokens, is_vl, is_reasoning, ... }, ... ] }
  → Returns: { models: [...], raw_configs: { model_id: full_entry, ... } }
```

### 7b. Caching

- In-memory cache per user_id + access_token combination
- Cache key: SHA256 of `qoder:{user_id_or_token}`
- TTL: 1 hour
- On cache miss or force_refresh: fetch from API
- On fetch failure: return stale cache if available

### 7c. Model Config Retrieval

`get_qoder_model_config(user_id, access_token, model_id)` — needed during chat request building to get the full `model_config` block.

### 7d. Model Map (`QODER_MODEL_MAP`)

Alias → canonical key mapping:

| Key | Description |
|-----|-------------|
| `auto` | Auto-select tier |
| `ultimate` | Ultimate tier |
| `performance` | Performance tier |
| `efficient` | Efficient tier |
| `lite` | Lite tier |
| `qmodel` | Frontier: QModel |
| `dmodel` | Frontier: DModel |
| `dfmodel` | Frontier: DFModel |
| `gm51model` | Frontier: GM51Model |
| `kmodel` | Frontier: KModel |
| `mmodel` | Frontier: MModel |

---

## 8. Handler (`handler.py`) — Core Proxy Logic

`QoderHandler` extends `BaseProviderHandler` with 5 overrides:

### 8a. `validate(api_key, data)`
- Minimal: only checks if token exists
- Real validation happens during chat request (because COSY signing is needed)

### 8b. `build_upstream_url(base_url, stream, data, model)`
- Always returns: `https://api3.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1`

### 8c. `build_headers(api_key, stream, data)`
- Build COSY-signed headers (with empty body — real signing in `build_request_body`)
- Requires: `userId` in data

### 8d. `build_request_body(model, body, data)` — **the complex one**
```
1. Resolve model key: "qd/auto" → "auto"
2. Get model_config from cache (fetch if missing — hard error if not found)
3. Transform: OpenAI body → Qoder body (transform.py)
4. JSON encode → WAF-bypass encode (encoding.py)
5. Build COSY headers with ENCODED body (cosy.py)
6. Add extra headers: X-Model-Key, X-Model-Source, Cache-Control, Accept, Accept-Encoding
7. Return: (encoded_bytes, signed_headers)
```

### 8e. `fetch_models(api_key, data)`
- Calls `resolve_qoder_models(credentials, force_refresh=True)`
- Returns normalized model list with `qoder/` prefix

### 8f. `unwrap_response(response_text)`
- Delegates to `transform.unwrap_qoder_response()`

---

## 9. End-to-End Chat Request Flow

```
Client → POST /v1/chat/completions { model: "qd/auto", messages: [...] }
  │
  ├─ 1. resolve_model_to_targets()
  │     - Alias "qd" → provider "qoder"
  │     - Find connection with access_token, userId, machineId
  │     - Build URL via handler.build_upstream_url()
  │     - Build initial headers via handler.build_headers()
  │
  ├─ 2. _build_provider_request()  [shared.py]
  │     - Check if handler has build_request_body()
  │     - Call handler.build_request_body(model, body, conn_data)
  │     - Returns: (encoded_bytes, signed_headers)
  │
  ├─ 3. Stream or Non-stream
  │     │
  │     ├─ Streaming: _stream_response()
  │     │   - Skip pre-flight check (Qoder always returns SSE)
  │     │   - Send: POST with content=encoded_bytes, headers=signed_headers
  │     │   - For each chunk: unwrap_qoder_sse_line() → forward to client
  │     │
  │     └─ Non-streaming: _non_stream_response()
  │         - Send: POST with content=encoded_bytes, headers=signed_headers
  │         - Unwrap response via handler.unwrap_response()
  │
  └─ 4. Usage tracking (async, after stream completes)
```

---

## 10. OAuth Handler (`oauth.py`)

`QoderOAuthHandler` extends `DeviceCodeHandler` (from `oauth_base.py`):

| Method | Behavior |
|--------|----------|
| `request_device_code()` | Calls `auth.initiate_device_flow()`, returns device code + verification URI |
| `poll_token()` | Calls `auth.poll_device_token()`, maps result to standard format |
| `post_exchange()` | Calls `auth.fetch_user_info()` for enrichment |
| `refresh_token()` | POST to center.qoder.sh refresh endpoint (usually 403) |
| `map_tokens()` | Maps to standard format: accessToken, refreshToken, expiresIn, email, displayName, providerSpecificData |

ProviderSpecificData stored in connection:
- `userId` — Qoder user ID (required for COSY)
- `machineId` — UUID machine ID (required for COSY)

---

## 11. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONNECTION SETUP                              │
│                                                                     │
│  Device Flow:                                                       │
│    initiate_device_flow → browser → poll_device_token → tokens      │
│                                                                     │
│  PAT Import:                                                        │
│    exchange_personal_token → fetch_user_info → connection data      │
│                                                                     │
│  Stored in DB (ProviderConnection.data JSON):                       │
│    { accessToken, refreshToken, userId, machineId, email, ... }     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        MODEL FETCHING                                │
│                                                                     │
│  fetch_models() → resolve_qoder_models() → fetch_qoder_catalog()   │
│     │                                                               │
│     ├─ COSY-sign GET /algo/api/v2/model/list                       │
│     ├─ Parse: { chat: [{ key, display_name, ... }] }               │
│     ├─ Cache: in-memory, 1h TTL, keyed by user_id+token            │
│     └─ Return: [{ id: "qoder/auto", name: "Auto", type: "llm" }]  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     CHAT REQUEST (core proxy)                        │
│                                                                     │
│  build_request_body(model, openai_body, conn_data)                  │
│     │                                                               │
│     ├─ 1. Resolve model_key: "qd/auto" → "auto"                    │
│     ├─ 2. Get model_config from cache (error if missing)            │
│     ├─ 3. transform.build_qoder_request_body() → Qoder JSON        │
│     ├─ 4. encoding.qoder_encode_body() → WAF-bypass encoded        │
│     ├─ 5. cosy.build_cosy_headers(body=encoded) → 17+ headers     │
│     └─ 6. Return (encoded_bytes, signed_headers)                   │
│                                                                     │
│  → POST https://api3.qoder.sh/algo/api/v2/.../agent_chat_generation│
│    ?FetchKeys=llm_model_result&AgentId=agent_common&Encode=1       │
│    Content: encoded_bytes                                           │
│    Headers: COSY-signed headers                                     │
│                                                                     │
│  Response unwrapping:                                               │
│    SSE: {"headers":{...},"body":"..."} → extract body → forward    │
│    JSON: {"statusCodeValue":200,"body":"..."} → extract body       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12. Key URLs

| Purpose | URL |
|---------|-----|
| Device login page | https://qoder.com/device/selectAccounts |
| Device token poll | https://openapi.qoder.sh/api/v1/deviceToken/poll |
| User info | https://openapi.qoder.sh/api/v1/userinfo |
| PAT exchange | https://openapi.qoder.sh/api/v1/jobToken/exchange |
| Token refresh | https://center.qoder.sh/algo/api/v3/user/refresh_token |
| Quota usage | https://openapi.qoder.sh/api/v2/quota/usage |
| Chat inference | https://api3.qoder.sh/algo/api/v2/service/pro/sse/agent_chat_generation |
| Model list | https://api3.qoder.sh/algo/api/v2/model/list |

---

## 13. Dependencies

- `cryptography` — RSA + AES encryption for COSY signing
- `httpx` — async HTTP client
- `pydantic` — schemas
- No external Qoder SDK — everything is manually ported from Node.js

---

## 14. Edge Cases & Gotchas

1. **Model config is required** — Qoder silently downgrades model if model_config is wrong/missing. Handler raises error if config is not found in cache.
2. **COSY signing with encoded body** — `build_headers()` is called with empty body (placeholder), actual signing happens in `build_request_body()` with encoded body.
3. **Token format varies** — Response can be `token`, `accessToken`, or `access_token`. Code handles all.
4. **User ID format varies** — Can be `id`, `uid`, or `userId`. Code handles all.
5. **No pre-flight for Qoder** — Endpoint always returns streaming SSE, so pre-flight check is skipped.
6. **Accept-Encoding: identity** — gzip triggers signature validation failure on Qoder CDN.
7. **Cache key collision risk** — Cache key is based on SHA256(`qoder:{user_id_or_token}`), unlikely collision.
8. **Non-stream = streaming** — Qoder always sends SSE format even for non-streaming requests. Handler unwraps + aggregates chunks.

---

## 15. 2026-06-09 Field Findings: Qoder PAT/OAuth and `Login expired`

### Scope of this finding

This section records what was actually observed in the local running app and
should override any earlier assumptions in this document about the 2026-06-09
incident.

Qoder supports **two valid connection methods** in 9Router:

1. **PAT import**: user provides `pt-...`, backend exchanges it via
   `/api/v1/jobToken/exchange`, stores a `jt-...` access token, `jrt-...`
   refresh token, generated `machineId`, `userId`, `displayName`, etc.
2. **OAuth/device flow**: backend starts Qoder device flow, polls device token,
   and stores the returned token plus generated/returned provider-specific data.

Do **not** conclude that PAT is unsupported. A newly imported PAT connection was
verified working.

### Observed database state

Existing Qoder connections used the same general PAT data shape:

```json
{
  "accessToken": "jt-...",
  "refreshToken": "jrt-...",
  "expiresAt": "2029-...",
  "displayName": "...",
  "userId": "...",
  "machineId": "...",
  "organizationId": "",
  "loginMethod": "pat",
  "models": []
}
```

A newly added PAT connection for profile `HanawatiBafasari bose` produced:

```text
provider=qoder
name=HanawatiBafasari bose
auth_type=apikey
accessToken=jt-JSb...
refreshToken=jrt-MMX...
machineId=dae03950-b0ba-44f1-b9c9-2399cce7fca1
loginMethod=pat
fetch models -> HTTP 200 OK, 11 models persisted
```

This proves the PAT path can still work with `jt-...` tokens and generated
`machineId`.

### Original failure

The failing connection was profile `Manda Mora`:

```text
provider=qoder
name=Manda Mora
auth_type=apikey
accessToken=jt-3Ha...
refreshToken=jrt-ed1...
machineId=a23c90a6-ed52-4ca3-9243-2ee05f8aad9f
loginMethod=pat
fetch models -> HTTP 403 {"code":"105","message":"Login expired"}
```

A direct upstream userinfo/status check for that old `jt-...` token returned an
inactive-token response during investigation:

```text
GET https://openapi.qoder.sh/api/v1/userinfo
Authorization: Bearer jt-3Ha...
-> 401 {"code":"TOKEN_EXPIRE","message":"token is not active"}
```

That evidence applies to the old `Manda Mora` token only. It must **not** be
generalized to all PAT tokens.

### qodercli capture facts

Local `qodercli` traffic showed Qoder uses multiple auth/header shapes depending
on endpoint:

1. Some account/status/region endpoints use plain bearer or signature headers.
2. `/algo` service endpoints such as chat generation use `Bearer COSY` headers.

Captured chat request headers included:

```text
Authorization: Bearer COSY.{payloadB64}.{sig}
Cosy-Business-Product: cli
Cosy-Business-Type: agent
Cosy-ClientType: 5
Cosy-Data-Policy: agree
Cosy-Date: <unix timestamp>
Cosy-Key: <RSA encrypted AES key>
Cosy-MachineId: <machine id>
Cosy-MachineToken: <machine id>
Cosy-MachineType: 5
Cosy-Scene: assistant
Cosy-User: <user id>
Cosy-Version: 1.0.14
Login-Version: v2
X-Model-Key: qmodel_latest
X-Model-Source: system
```

Important correction: `Bearer COSY` is **not inherently wrong** for Qoder
`/algo` service endpoints. Earlier notes that implied replacing all COSY auth
with simple bearer were incorrect.

### Current confirmed facts

- PAT import is a valid Qoder connection method.
- OAuth/device flow is also a valid Qoder connection method.
- 9Router must support both.
- A new PAT connection (`HanawatiBafasari bose`) successfully fetched 11 models.
- The old `Manda Mora` PAT connection returned `Login expired` during model
  fetch and its old token was observed as inactive by upstream userinfo.
- The failure should be treated as a stale/invalidated token or connection-state
  issue for that specific connection unless further evidence proves otherwise.
- Local `expiresAt` values are not sufficient proof that Qoder still accepts a
  token server-side.

### Practical debugging rule for future sessions

When investigating Qoder failures, always compare against a known-working Qoder
connection from the same environment before changing architecture or auth flow.

Minimum read-only checks:

1. Compare `ProviderConnection.data` for failing vs working Qoder connection.
2. Call upstream `userinfo` or equivalent validation for each token.
3. Call `fetch_qoder_catalog()` for each connection.
4. Check whether `models` were persisted in DB after fetch.
5. Only then decide whether the issue is signer/header logic, token expiry,
   refresh behavior, UI stale state, or DB state.

### Rollback note

Backup created before edits:

```bash
backups/qoder-provider-backup-20260609-163719.tar.gz
```

Last recorded commit before this investigation:

```bash
ca68b4f65a6e80021fe3f450ece3e4e888330be0
```

If rollback is needed, do not reset the whole repo blindly while user changes
exist. Restore only the relevant Qoder provider files or inspect the backup
first.
