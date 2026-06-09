# Provider "Add Connection" Flows — Investigation Report

> **Source**: Original 9router Next.js project at `/home/mint/dev/9router/`
> **Date**: 2026-05-19
> **Status**: Complete

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Provider Categories](#2-provider-categories)
3. [OAuth Providers — Add Connection Flow](#3-oauth-providers)
4. [Free Providers — Add Connection Flow](#4-free-providers)
5. [Free Tier Providers (API Key) — Add Connection Flow](#5-free-tier-providers)
6. [API Key Providers — Add Connection Flow](#6-api-key-providers)
7. [Web Cookie Providers — Add Connection Flow](#7-web-cookie-providers)
8. [Custom Compatible Providers — Add Connection Flow](#8-custom-compatible-providers)
9. [Provider-Specific Modals](#9-provider-specific-modals)
10. [API Endpoints Summary](#10-api-endpoints-summary)
11. [Key Differences from Current FastAPI Port](#11-key-differences)

---

## 1. Architecture Overview

### Provider Categories (from `src/shared/constants/providers.js`)

The original project defines providers in **6 categories**:

| Category | Constant | Auth Type | Count |
|----------|----------|-----------|-------|
| Free Providers | `FREE_PROVIDERS` | OAuth / No Auth | 5 (kiro, qwen, gemini-cli, iflow, opencode) |
| Free Tier Providers | `FREE_TIER_PROVIDERS` | API Key | 8 (openrouter, nvidia, ollama, vertex, gemini, cloudflare-ai, byteplus) |
| OAuth Providers | `OAUTH_PROVIDERS` | OAuth | 7 (claude, antigravity, codex, github, cursor, kilocode, cline) |
| API Key Providers | `APIKEY_PROVIDERS` | API Key | 60+ (openai, anthropic, deepseek, groq, etc.) |
| Web Cookie Providers | `WEB_COOKIE_PROVIDERS` | Browser Cookie | 2 (grok-web, perplexity-web) |
| Custom Compatible | Dynamic | API Key | OpenAI Compatible / Anthropic Compatible / Custom Embedding |

### Key Architectural Points

- **OAuth providers** use a completely different flow (OAuthModal) — NOT API key input
- **Free providers** like Kiro have their own custom auth modals (KiroAuthModal)
- **Cursor** has its own modal (CursorAuthModal) for importing tokens from local SQLite
- **GitLab** has its own modal (GitLabAuthModal) supporting both OAuth and PAT
- **Custom Compatible** providers are stored in `provider_nodes` table (not `providers`)
- The main API routes are:
  - `POST /api/providers` — Create API Key / Cookie connections
  - `GET/POST /api/oauth/[provider]/[action]` — OAuth flows (authorize, exchange, device-code, poll)

---

## 2. Provider Categories

### From `src/shared/constants/providers.js`:

```javascript
// Free Providers (no API key needed for some, OAuth for others)
FREE_PROVIDERS = { kiro, qwen, "gemini-cli", iflow, opencode }

// Free Tier Providers (API key, but have free access)
FREE_TIER_PROVIDERS = { openrouter, nvidia, ollama, vertex, gemini, "cloudflare-ai", byteplus }

// OAuth Providers (require OAuth flow)
OAUTH_PROVIDERS = { claude, antigravity, codex, github, cursor, kilocode, cline }

// API Key Providers (standard API key)
APIKEY_PROVIDERS = { openai, anthropic, deepseek, groq, xai, mistral, ... 60+ providers }

// Web Cookie Providers (use browser session cookie)
WEB_COOKIE_PROVIDERS = { "grok-web", "perplexity-web" }

// Custom Compatible (dynamic, stored in provider_nodes)
// Prefix: "openai-compatible-", "anthropic-compatible-", "custom-embedding-"
```

---

## 3. OAuth Providers

### 3.1 Claude (Authorization Code Flow + PKCE)

**Source**: `src/shared/components/OAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow**:
1. User clicks "Connect" on Claude provider card
2. `OAuthModal` opens with `provider="claude"`
3. Modal calls `GET /api/oauth/claude/authorize?redirect_uri=http://localhost:{port}/callback`
4. Backend generates PKCE code_verifier/code_challenge, returns `authUrl`
5. Modal opens popup to `authUrl` (https://claude.ai/oauth/authorize)
6. User authorizes in popup
7. Popup redirects to `/callback?code=...&state=...`
8. Callback page sends `postMessage` to parent window
9. Modal receives message, calls `POST /api/oauth/claude/exchange` with `{code, redirectUri, codeVerifier, state}`
10. Backend exchanges code for tokens, saves to DB
11. Modal shows success

**OAuth Config**:
```javascript
CLAUDE_CONFIG = {
  clientId: "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
  authorizeUrl: "https://claude.ai/oauth/authorize",
  tokenUrl: "https://api.anthropic.com/v1/oauth/token",
  scopes: ["org:create_api_key", "user:profile", "user:inference"],
  codeChallengeMethod: "S256",
}
```

**API Endpoints**:
- `GET /api/oauth/claude/authorize` → `{authUrl, codeVerifier, state}`
- `POST /api/oauth/claude/exchange` → `{success, connection}`

**Token Storage**: `accessToken`, `refreshToken`, `expiresAt` in `provider_connections` table

---

### 3.2 Codex (Authorization Code Flow + PKCE + Proxy)

**Source**: `src/shared/components/OAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow** (special — uses proxy server):
1. User clicks "Connect" on Codex provider card
2. `OAuthModal` opens with `provider="codex"`
3. Modal calls `GET /api/oauth/codex/authorize?redirect_uri=http://localhost:1455/auth/callback`
4. Backend generates PKCE, returns `authUrl`
5. **Codex uses fixed port 1455** for redirect
6. Modal calls `GET /api/oauth/codex/start-proxy?app_port={port}&state=...&code_verifier=...&redirect_uri=...`
7. If proxy starts successfully with `serverSide=true`:
   - Opens popup to authUrl
   - Polls `GET /api/oauth/codex/poll-status?state=...` until `status=done`
   - Proxy auto-exchanges tokens server-side
8. If proxy fails:
   - Falls back to manual callback URL input

**OAuth Config**:
```javascript
CODEX_CONFIG = {
  clientId: "app_EMoamEEZ73f0CkXaXp7hrann",
  authorizeUrl: "https://auth.openai.com/oauth/authorize",
  tokenUrl: "https://auth.openai.com/oauth/token",
  scope: "openid profile email offline_access",
  codeChallengeMethod: "S256",
  extraParams: {
    id_token_add_organizations: "true",
    codex_cli_simplified_flow: "true",
    originator: "codex_cli_rs",
  },
}
```

**API Endpoints**:
- `GET /api/oauth/codex/authorize` → `{authUrl, codeVerifier, state}`
- `GET /api/oauth/codex/start-proxy` → `{success, serverSide}`
- `GET /api/oauth/codex/poll-status?state=...` → `{status: "done"|"error"|...}`
- `POST /api/oauth/codex/exchange` → `{success, connection}`
- `GET /api/oauth/codex/stop-proxy` → `{success}`

---

### 3.3 GitHub Copilot (Device Code Flow)

**Source**: `src/shared/components/OAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow**:
1. User clicks "Connect" on GitHub provider card
2. `OAuthModal` opens with `provider="github"`
3. Modal detects `github` is in `deviceCodeProviders` list
4. Calls `GET /api/oauth/github/device-code`
5. Backend requests device code from GitHub: `POST https://github.com/login/device/code`
6. Returns `{device_code, user_code, verification_uri, interval}`
7. Modal shows:
   - Login URL (auto-opens in new tab)
   - User code (large, copyable)
   - "Waiting for authorization..." spinner
8. Modal polls `POST /api/oauth/github/poll` with `{deviceCode}` every interval seconds
9. When user authorizes in browser, poll returns `{success: true}`
10. Backend fetches copilot token from `https://api.github.com/copilot_internal/v2/token`
11. Saves connection

**OAuth Config**:
```javascript
GITHUB_CONFIG = {
  clientId: "Iv1.b507a08c87ecfe98",
  deviceCodeUrl: "https://github.com/login/device/code",
  tokenUrl: "https://github.com/login/oauth/access_token",
  userInfoUrl: "https://api.github.com/user",
  scopes: "read:user",
  apiVersion: "2022-11-28",
  copilotTokenUrl: "https://api.github.com/copilot_internal/v2/token",
  userAgent: "GitHubCopilotChat/0.26.7",
  editorVersion: "vscode/1.85.0",
  editorPluginVersion: "copilot-chat/0.26.7",
}
```

**API Endpoints**:
- `GET /api/oauth/github/device-code` → `{device_code, user_code, verification_uri, interval}`
- `POST /api/oauth/github/poll` → `{success, tokens}` or `{error, pending}`

---

### 3.4 Kiro (Multiple Auth Methods)

**Source**: `src/shared/components/KiroAuthModal.js`, `src/shared/components/KiroSocialOAuthModal.js`

**Flow** (most complex — 4 auth methods):
1. User clicks "Connect" on Kiro provider card
2. **KiroAuthModal** opens (NOT OAuthModal)
3. Shows method selection:
   - **AWS Builder ID** (recommended) → Device Code Flow
   - **AWS IAM Identity Center** → Device Code Flow with custom startUrl/region
   - **Google Account** (hidden) → Social OAuth via AWS Cognito
   - **GitHub Account** (hidden) → Social OAuth via AWS Cognito
   - **Import Token** → Auto-detect from AWS SSO cache or manual paste

**Method A: AWS Builder ID**
1. Calls `GET /api/oauth/kiro/device-code`
2. Backend registers client with AWS SSO OIDC, gets device code
3. Opens verification URL in new tab
4. Polls `POST /api/oauth/kiro/poll` with `{deviceCode, extraData: {_clientId, _clientSecret, _region, _authMethod, _startUrl}}`

**Method B: AWS IAM Identity Center**
1. User enters IDC Start URL and Region
2. Calls `GET /api/oauth/kiro/device-code?start_url=...&region=...&auth_method=idc`
3. Same device code flow as Builder ID but with custom SSO endpoint

**Method C: Import Token**
1. Auto-detects: `GET /api/oauth/kiro/auto-import` — reads from AWS SSO cache
2. If found, auto-fills refresh token
3. User clicks "Import Token": `POST /api/oauth/kiro/import` with `{refreshToken}`

**Method D: Social Login (Google/GitHub)**
1. **KiroSocialOAuthModal** opens
2. Calls `GET /api/oauth/kiro/social-authorize?provider=google|github`
3. Gets auth URL from AWS Cognito
4. Opens in new tab
5. User pastes callback URL (kiro:// scheme)
6. Calls `POST /api/oauth/kiro/social-exchange` with `{code, codeVerifier, provider}`

**OAuth Config**:
```javascript
KIRO_CONFIG = {
  ssoOidcEndpoint: "https://oidc.us-east-1.amazonaws.com",
  registerClientUrl: "https://oidc.us-east-1.amazonaws.com/client/register",
  deviceAuthUrl: "https://oidc.us-east-1.amazonaws.com/device_authorization",
  tokenUrl: "https://oidc.us-east-1.amazonaws.com/token",
  startUrl: "https://view.awsapps.com/start",
  socialAuthEndpoint: "https://prod.us-east-1.auth.desktop.kiro.dev",
  socialLoginUrl: "https://prod.us-east-1.auth.desktop.kiro.dev/login",
  socialTokenUrl: "https://prod.us-east-1.auth.desktop.kiro.dev/oauth/token",
  authMethods: ["builder-id", "idc", "google", "github", "import"],
}
```

**API Endpoints**:
- `GET /api/oauth/kiro/device-code` → `{device_code, user_code, verification_uri, _clientId, _clientSecret, _region, _authMethod, _startUrl}`
- `POST /api/oauth/kiro/poll` → `{success, tokens}` or `{error, pending}`
- `GET /api/oauth/kiro/auto-import` → `{found, refreshToken}` or `{error}`
- `POST /api/oauth/kiro/import` → `{success}` or `{error}`
- `GET /api/oauth/kiro/social-authorize?provider=...` → `{authUrl, codeVerifier}`
- `POST /api/oauth/kiro/social-exchange` → `{success}` or `{error}`

---

### 3.5 Cursor (Token Import from Local SQLite)

**Source**: `src/shared/components/CursorAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow** (no OAuth — token import only):
1. User clicks "Connect" on Cursor provider card
2. **CursorAuthModal** opens (NOT OAuthModal)
3. Auto-detects: `GET /api/oauth/cursor/auto-import`
   - Reads from Cursor IDE's SQLite database: `~/.config/Cursor/User/globalStorage/state.vscdb`
   - Keys: `cursorAuth/accessToken`, `storage.serviceMachineId`
4. If found, auto-fills both fields
5. If not found (or Windows), shows manual input
6. User clicks "Import Token": `POST /api/oauth/cursor/import` with `{accessToken, machineId}`

**Config**:
```javascript
CURSOR_CONFIG = {
  apiEndpoint: "https://api2.cursor.sh",
  chatEndpoint: "/aiserver.v1.ChatService/StreamUnifiedChatWithTools",
  tokenStoragePaths: {
    linux: "~/.config/Cursor/User/globalStorage/state.vscdb",
    macos: "/Users/<user>/Library/Application Support/Cursor/User/globalStorage/state.vscdb",
    windows: "%APPDATA%\\Cursor\\User\\globalStorage\\state.vscdb",
  },
  dbKeys: {
    accessToken: "cursorAuth/accessToken",
    machineId: "storage.serviceMachineId",
  },
}
```

**API Endpoints**:
- `GET /api/oauth/cursor/auto-import` → `{found, accessToken, machineId}` or `{windowsManual, error}`
- `POST /api/oauth/cursor/import` → `{success}` or `{error}`

---

### 3.6 Kilo Code (Custom Device Auth Flow)

**Source**: `src/shared/components/OAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow** (device code):
1. User clicks "Connect" on Kilo Code provider card
2. `OAuthModal` opens with `provider="kilocode"`
3. Modal detects `kilocode` is in `deviceCodeProviders` list
4. Calls `GET /api/oauth/kilocode/device-code`
5. Backend: `POST https://api.kilo.ai/api/device-auth/codes`
6. Returns device code + verification URL
7. Shows login URL + user code
8. Polls `POST /api/oauth/kilocode/poll` with `{deviceCode}`

**Config**:
```javascript
KILOCODE_CONFIG = {
  apiBaseUrl: "https://api.kilo.ai",
  initiateUrl: "https://api.kilo.ai/api/device-auth/codes",
  pollUrlBase: "https://api.kilo.ai/api/device-auth/codes",
}
```

---

### 3.7 Cline (Local Callback Flow)

**Source**: `src/shared/components/OAuthModal.js`, `src/lib/oauth/constants/oauth.js`

**Flow** (authorization code, no PKCE):
1. User clicks "Connect" on Cline provider card
2. `OAuthModal` opens with `provider="cline"`
3. Calls `GET /api/oauth/cline/authorize`
4. Backend: `GET https://api.cline.bot/api/v1/auth/authorize`
5. Returns auth URL
6. User authorizes, gets callback URL
7. User pastes callback URL
8. Calls `POST /api/oauth/cline/exchange` with `{code, redirectUri}` (NO codeVerifier)
9. Backend: `POST https://api.cline.bot/api/v1/auth/token`

**Config**:
```javascript
CLINE_CONFIG = {
  appBaseUrl: "https://app.cline.bot",
  apiBaseUrl: "https://api.cline.bot",
  authorizeUrl: "https://api.cline.bot/api/v1/auth/authorize",
  tokenExchangeUrl: "https://api.cline.bot/api/v1/auth/token",
  refreshUrl: "https://api.cline.bot/api/v1/auth/refresh",
}
```

---

## 4. Free Providers

### 4.1 Kiro AI
- Same as OAuth Kiro (section 3.4) — uses KiroAuthModal
- Marked as `deprecated: true` with risk notice

### 4.2 Qwen Code
- OAuth Device Code Flow with PKCE
- Marked as `deprecated: true` (discontinued by Alibaba on 2026-04-15)
- Uses same OAuthModal with device code flow

### 4.3 Gemini CLI
- OAuth flow (via Google)
- Marked as `deprecated: true` with risk notice

### 4.4 OpenCode Free
- **No auth required** (`noAuth: true`)
- Uses passthrough models from `https://opencode.ai/zen/v1/models`
- Just click "Connect" — no modal, no API key

### 4.5 iFlow
- OAuth flow with custom config
- Hidden in UI (`hidden: true`)

---

## 5. Free Tier Providers

These use **standard API key input** but may have free tiers:

| Provider | Extra Fields | Notes |
|----------|-------------|-------|
| OpenRouter | None | Free tier: 27+ free models, 200 req/day |
| NVIDIA NIM | None | Free for NVIDIA Developer Program |
| Ollama Cloud | None | Free tier: light usage |
| Vertex AI | None | $300 free credits for new GCP accounts |
| Gemini | None | Free tier: 15 RPM, 1M tokens/day |
| Cloudflare | `accountId` (providerSpecificData) | Workers AI free tier |
| BytePlus | None | Free credits for new accounts |

**Cloudflare** has special handling:
- `hasProviderSpecificData: true`
- Requires `accountId` in `providerSpecificData`
- EditConnectionModal shows Account ID field

---

## 6. API Key Providers

### Standard Flow
1. User clicks provider card
2. Shows API key input modal (inline on the card or in a modal)
3. User enters API key
4. Calls `POST /api/providers` with `{provider, apiKey, name}`
5. Backend validates and saves

### Providers with Special Fields

**Azure OpenAI** (`hasProviderSpecificData: true`):
- `azureEndpoint` — e.g., `https://your-resource.openai.azure.com`
- `apiVersion` — default `2024-10-01-preview`
- `deployment` — e.g., `gpt-4`
- `organization` — billing org ID

**Cloudflare AI** (`hasProviderSpecificData: true`):
- `accountId` — Cloudflare account ID

**Web Cookie Providers** (grok-web, perplexity-web):
- `authType: "cookie"` instead of API key
- `authHint` shown to user
- Stored as cookie value, not API key

---

## 7. Web Cookie Providers

### Grok Web / Perplexity Web
- Auth type: `cookie`
- User pastes browser session cookie value
- `authHint` shown in UI (e.g., "Paste your sso= cookie value from grok.com")
- Stored same as API key but with `authType: "cookie"`

---

## 8. Custom Compatible Providers

### Flow for "Add OpenAI Compatible"
1. User clicks "Add OpenAI Compatible" button on providers page
2. Modal opens asking for:
   - Name (required)
   - Base URL (required)
   - API Key
   - API Type (optional)
3. Backend creates entry in `provider_nodes` table with `type: "openai-compatible"`
4. Provider ID format: `openai-compatible-{name}`
5. Connection created with provider ID referencing the node

### Flow for "Add Anthropic Compatible"
1. User clicks "Add Anthropic Compatible" button
2. Similar modal with:
   - Name
   - Base URL
   - API Key
3. Backend creates entry in `provider_nodes` table with `type: "anthropic-compatible"`
4. Provider ID format: `anthropic-compatible-{name}`

### Custom Embedding Providers
- Provider ID format: `custom-embedding-{name}`
- Similar flow for embedding-specific endpoints

### Storage
- **provider_nodes** table: stores the node definition (name, baseUrl, apiType, prefix)
- **provider_connections** table: stores the connection (apiKey, linked to node via provider ID)

---

## 9. Provider-Specific Modals

| Modal | Used By | Source File |
|-------|---------|-------------|
| `OAuthModal` | Claude, Codex, GitHub, Qwen, Kilo Code, Cline | `src/shared/components/OAuthModal.js` |
| `KiroAuthModal` | Kiro (all methods) | `src/shared/components/KiroAuthModal.js` |
| `KiroSocialOAuthModal` | Kiro (Google/GitHub social) | `src/shared/components/KiroSocialOAuthModal.js` |
| `CursorAuthModal` | Cursor | `src/shared/components/CursorAuthModal.js` |
| `GitLabAuthModal` | GitLab Duo | `src/shared/components/GitLabAuthModal.js` |
| `EditConnectionModal` | All (edit existing) | `src/shared/components/EditConnectionModal.js` |
| `ComboFormModal` | Combo providers | `src/shared/components/ComboFormModal.js` |
| `ManualConfigModal` | Manual config display | `src/shared/components/ManualConfigModal.js` |

---

## 10. API Endpoints Summary

### OAuth Routes (`src/app/api/oauth/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/oauth/[provider]/authorize` | GET | Generate OAuth auth URL (PKCE) |
| `/api/oauth/[provider]/exchange` | POST | Exchange code for tokens |
| `/api/oauth/[provider]/device-code` | GET | Request device code |
| `/api/oauth/[provider]/poll` | POST | Poll for device code token |
| `/api/oauth/codex/start-proxy` | GET | Start Codex proxy server |
| `/api/oauth/codex/stop-proxy` | GET | Stop Codex proxy server |
| `/api/oauth/codex/poll-status` | GET | Poll Codex proxy status |
| `/api/oauth/kiro/auto-import` | GET | Auto-detect Kiro token |
| `/api/oauth/kiro/import` | POST | Import Kiro refresh token |
| `/api/oauth/kiro/social-authorize` | GET | Kiro social auth URL |
| `/api/oauth/kiro/social-exchange` | POST | Kiro social auth exchange |
| `/api/oauth/cursor/auto-import` | GET | Auto-detect Cursor tokens |
| `/api/oauth/cursor/import` | POST | Import Cursor tokens |
| `/api/oauth/gitlab/pat` | POST | GitLab PAT auth |

### Provider Routes (`src/app/api/providers/`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/providers` | GET | List all connections |
| `/api/providers` | POST | Create API key/cookie connection |
| `/api/providers/[id]` | GET | Get single connection |
| `/api/providers/[id]` | PUT | Update connection |
| `/api/providers/[id]` | DELETE | Delete connection |
| `/api/providers/[id]/test` | POST | Test connection |
| `/api/providers/validate` | POST | Validate API key |
| `/api/providers/test-batch` | POST | Batch test connections |
| `/api/provider-nodes` | GET | List custom provider nodes |
| `/api/provider-nodes` | POST | Create custom provider node |

---

## 11. Key Differences from Current FastAPI Port

### Current FastAPI Port Issues

1. **Generic API key template for all providers** — WRONG
   - OAuth providers (Claude, Codex, GitHub, etc.) need OAuth flow, not API key input
   - Kiro needs multi-method auth (Builder ID, IDC, Import, Social)
   - Cursor needs token import from local SQLite
   - GitLab supports both OAuth and PAT

2. **Missing OAuth flow entirely**
   - No `OAuthModal` component
   - No `/api/oauth/[provider]/[action]` endpoints
   - No PKCE generation
   - No device code flow support

3. **Missing provider-specific modals**
   - No `KiroAuthModal`
   - No `CursorAuthModal`
   - No `GitLabAuthModal`
   - No `KiroSocialOAuthModal`

4. **Missing callback page**
   - Original has `/callback` page that receives OAuth redirects
   - Sends data via postMessage, BroadcastChannel, localStorage

5. **Missing token refresh**
   - Original has `src/sse/services/tokenRefresh.js`
   - Handles automatic token refresh for OAuth connections

6. **Custom providers stored differently**
   - Original: `provider_nodes` table + `provider_connections` table
   - FastAPI port may not have this separation

### What Needs to Be Implemented

1. **OAuth infrastructure**:
   - PKCE generation utility
   - Device code flow utility
   - Token exchange utility
   - OAuth config constants for each provider

2. **OAuth API endpoints**:
   - Dynamic route: `/api/oauth/{provider}/{action}`
   - Provider-specific endpoints (kiro, cursor, gitlab)

3. **Frontend modals**:
   - `OAuthModal` — generic OAuth flow with popup + manual fallback
   - `KiroAuthModal` — multi-method auth selection
   - `CursorAuthModal` — token import with auto-detect
   - `GitLabAuthModal` — OAuth + PAT dual mode
   - `KiroSocialOAuthModal` — social login with manual callback

4. **Callback page**:
   - `/callback` route that receives OAuth redirects
   - Sends data to parent window via postMessage/BroadcastChannel/localStorage

5. **Provider card UI changes**:
   - OAuth providers should show "Connect" button (not API key input)
   - Free providers (opencode) should auto-connect
   - Different UI for different auth types

---

## Source File Reference

| Component | Path |
|-----------|------|
| Provider constants | `src/shared/constants/providers.js` |
| OAuth configs | `src/lib/oauth/constants/oauth.js` |
| OAuth service | `src/lib/oauth/services/oauth.js` |
| OAuthModal | `src/shared/components/OAuthModal.js` |
| KiroAuthModal | `src/shared/components/KiroAuthModal.js` |
| KiroSocialOAuthModal | `src/shared/components/KiroSocialOAuthModal.js` |
| CursorAuthModal | `src/shared/components/CursorAuthModal.js` |
| GitLabAuthModal | `src/shared/components/GitLabAuthModal.js` |
| EditConnectionModal | `src/shared/components/EditConnectionModal.js` |
| Providers page | `src/app/(dashboard)/dashboard/providers/page.js` |
| New provider page | `src/app/(dashboard)/dashboard/providers/new/page.js` |
| Providers API | `src/app/api/providers/route.js` |
| OAuth dynamic route | `src/app/api/oauth/[provider]/[action]/route.js` |
| Callback page | `src/app/callback/page.js` |
| Provider store | `src/store/providerStore.js` |
