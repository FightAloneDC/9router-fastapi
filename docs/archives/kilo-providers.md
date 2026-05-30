# Kilo Providers — Kilo Code & Kilo Gateway

> **Created:** 2026-05-19
> **Status:** Complete

---

## Overview

9Router supports two Kilo providers that share a common `kilo` prefix for model routing but use different authentication methods:

| Provider | ID | Alias | Auth Type | Base URL |
|----------|-----|-------|-----------|----------|
| **Kilo Code** | `kilocode` | `kc` | OAuth (Device Code flow) | `https://api.kilo.ai/api/openrouter` |
| **Kilo Gateway** | `kilo-gateway` | `kg` | API Key (Bearer token) | `https://api.kilo.ai/api/gateway` |

Both providers share:
- **Model prefix:** `kilo` (for routing)
- **Model format:** `provider/model` (e.g., `anthropic/claude-sonnet-4`)
- **Usage/credit calculation:** Same for both

---

## Kilo Code (OAuth)

### Authentication: Device Code Flow

Kilo Code uses a custom Device Code flow (not standard OAuth2 PKCE):

1. **Initiate** — POST to `https://api.kilo.ai/api/device-auth/codes`
   - Returns: `code`, `verificationUrl`, `expiresIn`
   - No body required, no PKCE challenge

2. **User Authorization** — User opens `verificationUrl` in browser and approves

3. **Poll for Token** — GET `https://api.kilo.ai/api/device-auth/codes/{code}`
   - HTTP 202 → authorization pending (keep polling)
   - HTTP 200 with `status: "approved"` → token in response
   - HTTP 403 → user denied
   - HTTP 410 → code expired
   - Poll interval: 3 seconds

4. **Token Exchange** — On success, the response contains:
   - `access_token` — used as Bearer token for API calls
   - `userEmail` — stored for display
   - `organizations[0].id` — org ID fetched from `/api/profile`

### Model Routing

Kilo Code routes through OpenRouter. The proxy config maps:
- Alias `kc` → provider ID `kilocode`
- Base URL from OAuth token: `https://api.kilo.ai/api/openrouter`
- Request format: OpenAI-compatible

### Frontend Configuration

```javascript
// OAuth providers (frontend/src/constants/providers.js)
kilocode: {
  id: "kilocode",
  alias: "kc",
  name: "Kilo Code",
  icon: "Code",
  color: "#FF6B35",
  textIcon: "KC",
  website: "https://kilocode.ai",
  notice: { signupUrl: "https://kilocode.ai" }
}
```

### Known Limitations

- **Test connection:** Not supported (same as original 9router)
- **Fetch models:** Not supported (same as original 9router)
- **Test model:** Works — can send chat requests through the proxy

---

## Kilo Gateway (API Key)

### Authentication: API Key (Bearer Token)

Standard API key authentication:

1. User provides their Kilo API key
2. All requests include `Authorization: Bearer <key>` header
3. Key can be obtained from https://kilo.ai

### Provider Configuration (Backend)

```python
# proxy.py — PROVIDER_CONFIGS
"kilo-gateway": {
    "base_url": "https://api.kilo.ai/api/gateway",
    "format": "openai",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer ",
}
```

```python
# proxy.py — ALIAS_TO_ID
"kg": "kilo-gateway",
```

### Model Routing

- Alias `kg` → provider ID `kilo-gateway`
- Base URL: `https://api.kilo.ai/api/gateway`
- Endpoint: `/chat/completions` (OpenAI-compatible)
- Request format: OpenAI-compatible

### Fetch Models

Fetches available models without authentication:

```
GET https://api.kilo.ai/api/gateway/models
```

Returns a list of available models. Configured in frontend as:

```javascript
modelsFetcher: {
  url: "https://api.kilo.ai/api/gateway/models",
  type: "kilo-gateway"
}
```

### Test Connection

Tests connectivity by sending a minimal chat request:

```
POST https://api.kilo.ai/api/gateway/chat/completions
Headers: Authorization: Bearer <api-key>
         Content-Type: application/json
Body: {
  "model": "kilo-auto/free",
  "messages": [{"role": "user", "content": "ping"}],
  "max_tokens": 1
}
```

If the request succeeds (HTTP 200), the connection is valid.

### Frontend Configuration

```javascript
// API key providers (frontend/src/constants/providers.js)
"kilo-gateway": {
  id: "kilo-gateway",
  alias: "kg",
  name: "Kilo Gateway",
  icon: "Code",
  color: "#FF6B35",
  textIcon: "KG",
  website: "https://kilo.ai",
  notice: { apiKeyUrl: "https://kilo.ai" },
  passthroughModels: true,
  modelsFetcher: {
    url: "https://api.kilo.ai/api/gateway/models",
    type: "kilo-gateway"
  },
  serviceKinds: ["llm"]
}
```

---

## API Endpoints

### Chat Completions (both providers)

```
POST /v1/chat/completions
Authorization: Bearer <9router-token>
Content-Type: application/json

{
  "model": "kc/anthropic/claude-sonnet-4",   // Kilo Code
  // or "kg/anthropic/claude-sonnet-4",      // Kilo Gateway
  "messages": [{"role": "user", "content": "Hello"}]
}
```

The prefix (`kc` or `kg`) tells 9Router which provider to route to.

### Model Fetching (Kilo Gateway only)

```
GET /api/providers/kilo-gateway/models
Authorization: Bearer <9router-token>
```

Proxies to `https://api.kilo.ai/api/gateway/models`.

---

## Source Code Reference

| Component | File | Key Lines |
|-----------|------|-----------|
| Alias mapping | `backend/app/services/proxy.py` | L39 (`kc`), L82 (`kg`) |
| Gateway config | `backend/app/services/proxy.py` | L309-314 |
| OAuth config | `backend/app/services/oauth.py` | L230-235 |
| Device code flow | `backend/app/services/oauth.py` | L1550-1571 |
| Token polling | `backend/app/services/oauth.py` | L1574-1612 |
| Frontend defs | `frontend/src/constants/providers.js` | L46, L88 |
| Device code providers | `frontend/src/components/OAuthModal.jsx` | L14 |

---

## Quick Reference

### Adding a Kilo Code Connection
1. Click "Add Connection" → Select "Kilo Code"
2. A device code + verification URL appears
3. Open the URL in browser, approve authorization
4. Token is automatically retrieved and stored

### Adding a Kilo Gateway Connection
1. Click "Add Connection" → Select "Kilo Gateway"
2. Enter your API key from https://kilo.ai
3. Models are auto-fetched from the gateway
4. Connection is validated via test chat with `kilo-auto/free`

### Using Kilo Models
```
# Via Kilo Code (OAuth)
kc/anthropic/claude-sonnet-4

# Via Kilo Gateway (API key)
kg/anthropic/claude-sonnet-4
```
