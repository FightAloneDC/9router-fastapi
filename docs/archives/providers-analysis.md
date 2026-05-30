# Providers Page — Analisis Lengkap dari Projek Asli (Next.js)

> Generated: 2026-05-18
> Source: `/home/mint/dev/9router/src/`

---

## 1. Struktur Halaman

### Route Hierarchy
```
/dashboard/providers              → Main providers list page (page.js)
/dashboard/providers/new          → New provider creation page (page.js)
/dashboard/providers/[id]         → Provider detail page (page.js)
```

### Main Page Layout (`providers/page.js`)
The main page displays providers grouped by auth type, each in a Card section:
1. **Custom Providers** — OpenAI Compatible + Anthropic Compatible (from provider-nodes API)
2. **OAuth Providers** — Claude, Codex, GitHub Copilot, Kiro, Cursor, Kilo Code, Cline, GitLab, CodeBuddy
3. **Free Providers** — Kiro, Qwen, Gemini CLI, iFlow, OpenCode
4. **Free Tier Providers** — OpenRouter, NVIDIA, Ollama, Vertex, Gemini, etc.
5. **API Key Providers** — OpenAI, Anthropic, DeepSeek, Groq, etc. (initially shows top 8, "Show all" button)

Each provider entry shows:
- Provider icon + name
- Status badges: "N Connected" (green), "N Error (CODE)" (red)
- Toggle switch to enable/disable all connections
- "Test All" button for batch testing
- Link to detail page

### Detail Page Layout (`providers/[id]/page.js`)
The detail page has several sections:
1. **Header** — Provider name, icon, website link, alias
2. **Connections Section** — List of ConnectionRow components
   - Each connection shows: name/email, status badge, priority, proxy info, cooldown timer
   - Actions: toggle active, move up/down, edit, delete, proxy pool assignment
3. **Models Section** — ModelRow components for static models + PassthroughModelsSection + CompatibleModelsSection
   - Each model shows: ID, name, copy button, test button
   - Custom model support (add custom model modal)
   - Disable/enable individual models
4. **Provider Strategy** — Fallback strategy selector (round-robin, priority-based)
5. **Thinking Mode** — Auto/extended thinking config

### New Provider Page (`providers/new/page.js`)
Simple form with: Provider selector, Auth Method (api_key/oauth), API Key input, Display Name, Active toggle.

---

## 2. Provider Types & Classification

### Source: `src/shared/constants/providers.js`

Providers are organized into **5 categories** (each is a separate exported object):

| Category | Export | Auth Type | Count | Examples |
|---|---|---|---|---|
| **Free** | `FREE_PROVIDERS` | OAuth/noAuth | ~6 | kiro, qwen, gemini-cli, iflow, opencode |
| **Free Tier** | `FREE_TIER_PROVIDERS` | API Key | ~6 | openrouter, nvidia, ollama, vertex, gemini |
| **OAuth** | `OAUTH_PROVIDERS` | OAuth | ~10 | claude, codex, github, cursor, kilocode, cline, gitlab, codebuddy |
| **API Key** | `APIKEY_PROVIDERS` | API Key | ~50+ | openai, anthropic, deepseek, groq, xai, mistral, etc. |
| **Web Cookie** | `WEB_COOKIE_PROVIDERS` | Cookie | 2 | grok-web, perplexity-web |

### Combined: `AI_PROVIDERS`
```js
export const AI_PROVIDERS = { ...FREE_PROVIDERS, ...FREE_TIER_PROVIDERS, ...OAUTH_PROVIDERS, ...APIKEY_PROVIDERS, ...WEB_COOKIE_PROVIDERS };
```

### Provider Object Shape (per entry)
```js
{
  id: "openai",           // Unique provider ID
  alias: "openai",        // Short alias for routing (prefix)
  name: "OpenAI",         // Display name
  icon: "auto_awesome",   // Material icon name
  color: "#10A37F",       // Brand color
  textIcon: "OA",         // Text fallback for icon
  website: "https://...",  // Provider website
  notice: { apiKeyUrl: "..." }, // Notice text + link for API key page
  hidden: false,           // Hide from UI
  deprecated: false,       // Show deprecation warning
  deprecationNotice: "...", // Deprecation message
  noAuth: false,           // No authentication needed
  passthroughModels: false, // Models are fetched dynamically
  serviceKinds: ["llm"],   // Service types: llm, tts, embedding, stt, image, etc.
  thinkingConfig: {},       // Thinking/reasoning config
  modelsFetcher: { url, type }, // For fetching suggested models
  hasProviderSpecificData: false, // Needs extra config fields (Azure, etc.)
  authType: "cookie",      // For web cookie providers
  authHint: "...",         // Hint text for cookie input
  mediaPriority: 1,        // Sort order for media providers
  ttsConfig: {},           // TTS-specific config
  sttConfig: {},           // STT-specific config
  embeddingConfig: {},     // Embedding-specific config
  searchConfig: {},        // Web search config
  fetchConfig: {},         // Web fetch config
  imageConfig: {},         // Image generation config
}
```

---

## 3. Prefix System

### Prefix Constants
```js
export const OPENAI_COMPATIBLE_PREFIX = "openai-compatible-";
export const ANTHROPIC_COMPATIBLE_PREFIX = "anthropic-compatible-";
export const CUSTOM_EMBEDDING_PREFIX = "custom-embedding-";
```

### How Prefixes Work
- **Built-in providers**: Use their `alias` field as prefix (e.g., `openai`, `ds` for DeepSeek, `gc` for Gemini CLI)
- **Custom compatible providers**: ID is generated as `${PREFIX}${apiType}-${generateId()}` (e.g., `openai-compatible-chat-a1b2c3`)
- **Model routing format**: `prefix/model-name` (e.g., `openai/gpt-4o`, `ds/deepseek-chat`, `openai-compatible-chat-abc123/gpt-4o`)

### Alias System
```js
// Helper: Get provider by alias
export function getProviderByAlias(alias) { ... }
// Helper: Get provider ID from alias
export function resolveProviderId(aliasOrId) { ... }
// Helper: Get alias from provider ID
export function getProviderAlias(providerId) { ... }

// Mappings
export const ALIAS_TO_ID = { alias → id };
export const ID_TO_ALIAS = { id → alias };
```

### Provider Normalization (`src/lib/providerNormalization.js`)
```js
// Normalizes provider ID from various formats
export function normalizeProviderId(provider) {
  // 1. Direct lookup in AI_PROVIDERS
  // 2. Slugify and lookup (lowercase, hyphens)
  // 3. Match by name (case-insensitive)
  // 4. Return as-is if not found
}

// Normalizes provider-specific data (e.g., ollama-local baseUrl)
export function normalizeProviderSpecificData(provider, body, providerSpecificData) { ... }
```

### Detection Helpers
```js
export function isOpenAICompatibleProvider(providerId) { return providerId.startsWith("openai-compatible-"); }
export function isAnthropicCompatibleProvider(providerId) { return providerId.startsWith("anthropic-compatible-"); }
export function isCustomEmbeddingProvider(providerId) { return providerId.startsWith("custom-embedding-"); }
```

---

## 4. Model Management (Fetch, Store, Display)

### Model Sources
1. **Static models** — `src/shared/constants/models.js` (`getModelsByProviderId()`)
2. **Suggested models** — Fetched via `modelsFetcher` config from provider definition
3. **Passthrough models** — Dynamically fetched from provider's `/v1/models` endpoint
4. **Compatible models** — Fetched from custom compatible provider's models endpoint
5. **Custom models** — User-added via AddCustomModelModal

### Suggested Models Fetcher (`src/shared/utils/providerModelsFetcher.js`)
```js
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 min cache

export async function fetchSuggestedModels(fetcher) {
  // fetcher = { url, type } from provider config
  // Calls /api/providers/suggested-models?url=...&type=...
  // Filters: "openrouter-free" (free models, 200k+ context), "opencode-free" (models ending in -free)
}
```

### Models API Route (`/api/providers/[id]/models`)
- Fetches models from provider's API endpoint
- Handles provider-specific parsing: OpenAI style, Gemini CLI, Codex (adds -review variants), Qwen, Kiro
- For OAuth providers: uses access token for auth
- For API key providers: uses stored API key
- For compatible providers: uses stored baseUrl + API key

### Model Test Flow
- `POST /api/providers/[id]/test-models` — Tests individual models via `/api/v1/chat/completions`
- Sends `{ model: modelId, max_tokens: 1, messages: [{role:"user", content:"hi"}] }`
- 200 = working, 400 = auth passed (model reachable), other = error
- Returns `{ ok, latencyMs, error }` per model

### Model Disable System
- `GET /api/models/disabled?providerAlias=...` — Get disabled model IDs
- `POST /api/models/disabled` — Disable models `{ providerAlias, ids: [...] }`
- `DELETE /api/models/disabled?providerAlias=...&id=...` — Enable specific model
- `DELETE /api/models/disabled?providerAlias=...` — Enable all models

### Model Alias System
- `GET /api/models/alias` — Get all model aliases
- Aliases map custom names to `provider/model` format

---

## 5. Connection CRUD

### Database Model
Connection = ProviderConnection record with fields:
- `id` (UUID)
- `provider` (provider ID string)
- `authType` ("oauth" | "apikey" | "cookie")
- `name` (display name)
- `email` (from OAuth)
- `apiKey` (encrypted for API key providers)
- `accessToken`, `refreshToken`, `idToken` (for OAuth)
- `expiresAt` (token expiry)
- `isActive` (boolean toggle)
- `priority` (number, for connection ordering)
- `globalPriority` (global priority across providers)
- `defaultModel` (default model for this connection)
- `testStatus` ("active" | "success" | "error" | "expired" | "unavailable")
- `lastError`, `lastErrorAt`, `errorCode`, `lastErrorType`
- `lastUsedAt`, `consecutiveUseCount`
- `providerSpecificData` (JSON: baseUrl, azureEndpoint, deployment, proxyPoolId, etc.)
- `createdAt`, `updatedAt`

### API Endpoints

#### `GET /api/providers` — List all connections
- Returns all connections with sensitive fields removed (apiKey, accessToken, refreshToken hidden)
- Enriches compatible provider names from provider-nodes

#### `POST /api/providers` — Create connection
```json
{
  "provider": "openai",
  "authType": "apikey",
  "apiKey": "sk-...",
  "name": "My OpenAI Key",
  "priority": 1,
  "isActive": true,
  "defaultModel": "gpt-4o",
  "providerSpecificData": { "baseUrl": "..." },
  "connectionProxyEnabled": false,
  "connectionProxyUrl": "",
  "proxyPoolId": null
}
```
- Normalizes provider ID via `normalizeProviderId()`
- Validates proxy config
- For OAuth: stores accessToken, refreshToken, email
- For API Key: validates via `/api/providers/validate` before saving

#### `GET /api/providers/[id]` — Get single connection
- Returns connection with sensitive fields removed

#### `PUT /api/providers/[id]` — Update connection
- Can update: name, priority, isActive, defaultModel, proxyPoolId, providerSpecificData
- Merges providerSpecificData with existing

#### `DELETE /api/providers/[id]` — Delete connection

#### `GET /api/providers/client` — Dashboard-safe list (whitelist only)
- Returns only safe metadata fields (no secrets)
- Masks names that look like API keys

### Provider Nodes API (for Custom Compatible providers)

#### `GET /api/provider-nodes` — List all provider nodes
#### `POST /api/provider-nodes` — Create provider node
```json
{
  "name": "My Custom Provider",
  "prefix": "my-provider",
  "apiType": "chat",  // "chat" | "responses" (for openai-compatible)
  "baseUrl": "https://api.example.com/v1",
  "type": "openai-compatible"  // "openai-compatible" | "anthropic-compatible" | "custom-embedding"
}
```
- Generates ID: `${PREFIX}${apiType}-${generateId()}`
- Creates node + returns it

#### `PUT /api/provider-nodes/[id]` — Update provider node
- Updates name, prefix, baseUrl, apiType
- Propagates changes to all connections of this provider

#### `DELETE /api/provider-nodes/[id]` — Delete provider node
- Also deletes all connections for this provider

#### `POST /api/provider-nodes/validate` — Validate API key against base URL
- Tests `/v1/models` endpoint first, falls back to `/v1/chat/completions`
- For custom-embedding: tests `/embeddings` directly

---

## 6. API Key Test & Save Flow

### Test Single Connection (`POST /api/providers/[id]/test`)
Located in `testUtils.js`:

1. **For OAuth providers** (claude, codex, gemini-cli, github, etc.):
   - Check token expiry first
   - If expired and refreshable → attempt token refresh
   - If not refreshable → mark as expired
   - Provider-specific test endpoints (e.g., codex hits `chatgpt.com/backend-api/codex/responses`)
   - Accept 400 as "auth passed" for some providers

2. **For API key providers**:
   - Hit provider's default model via `/v1/chat/completions` with `max_tokens: 1`
   - Or use provider-specific validation endpoint
   - For web-only providers (webSearch/webFetch): probe searchConfig/fetchConfig
   - For media providers (tts/embedding/stt): probe *Config endpoints

3. **For compatible providers**:
   - Use stored baseUrl + API key
   - Hit `/v1/models` or `/v1/chat/completions`

4. **Result**: Updates connection's `testStatus`, `lastError`, `errorCode`, `lastErrorAt`

### Batch Test (`POST /api/providers/test-batch`)
```json
{ "mode": "all" | "oauth" | "free" | "apikey" | "compatible" | "provider", "providerId": "..." }
```
- Tests all active connections matching the mode
- Returns `{ results: [...], summary: { passed, failed, total } }`

### Validate API Key (`POST /api/providers/validate`)
Used when creating new connections:
- For web providers: probes searchConfig/fetchConfig
- For media providers: probes *Config endpoints
- For LLM providers: hits `/v1/models` then `/v1/chat/completions` as fallback
- Returns `{ valid: true/false, error: "...", modelCount: N }`

### Save Flow (UI)
1. User enters API key in AddApiKeyModal
2. Modal calls `POST /api/providers/validate` first
3. If valid → shows success + model count
4. User clicks "Save" → calls `POST /api/providers` with apiKey + provider
5. Connection created → refreshes connection list

### Bulk Add (AddApiKeyModal)
- Supports bulk mode: paste multiple keys in `name|key` format
- Each key validated individually
- Shows success/failed count

---

## 7. OAuth Flow (per provider)

### Flow Types
| Flow Type | Providers | Steps |
|---|---|---|
| `authorization_code_pkce` | claude, codex, gitlab | 1. Generate PKCE → 2. Build auth URL → 3. User authorizes → 4. Exchange code |
| `authorization_code` | gemini-cli, antigravity, iflow, qoder, cline | 1. Build auth URL → 2. User authorizes → 3. Exchange code (+client_secret) |
| `device_code` | qwen, github, kiro, kimi-coding, kilocode, codebuddy | 1. Request device code → 2. Show user code + URL → 3. Poll for token |
| `import_token` | cursor | 1. User imports token from IDE's SQLite DB |

### OAuth API Route: `/api/oauth/[provider]/[action]`

#### `GET /api/oauth/[provider]/authorize`
- Generates PKCE (code_verifier, code_challenge, state)
- Returns `{ authUrl, state, codeVerifier, codeChallenge, redirectUri, flowType }`

#### `POST /api/oauth/[provider]/exchange`
- Exchanges authorization code for tokens
- Calls provider's `exchangeToken()` then `postExchange()` then `mapTokens()`
- Creates provider connection in database
- Returns `{ success, connection }`

#### `GET /api/oauth/[provider]/device-code`
- Requests device code from provider
- Returns `{ device_code, user_code, verification_uri, verification_uri_complete, expires_in, interval }`

#### `POST /api/oauth/[provider]/poll`
- Polls for device code authorization
- Returns `{ success, tokens }` or `{ error, pending: true }`

### Per-Provider OAuth Details

#### Claude (authorization_code_pkce)
- Client ID: `9d1c250a-e61b-44d9-88ed-5944d1962f5e`
- Authorize: `https://claude.ai/oauth/authorize`
- Token: `https://api.anthropic.com/v1/oauth/token`
- Scopes: `org:create_api_key user:profile user:inference`

#### Codex/OpenAI (authorization_code_pkce)
- Client ID: `app_EMoamEEZ73f0CkXaXp7hrann`
- Authorize: `https://auth.openai.com/oauth/authorize`
- Token: `https://auth.openai.com/oauth/token`
- Fixed port: 1455, callback: `/auth/callback`
- Extracts email + ChatGPT account info from id_token

#### Gemini CLI (authorization_code)
- Google OAuth with client_secret
- Fetches projectId from `cloudcode-pa.googleapis.com`
- Scopes: cloud-platform, userinfo.email, userinfo.profile

#### GitHub Copilot (device_code)
- Client ID: `Iv1.b507a08c87ecfe98`
- Device code: `https://github.com/login/device/code`
- Post-exchange: fetches Copilot token from `/copilot_internal/v2/token`
- Stores: copilotToken, copilotTokenExpiresAt, githubLogin, githubName

#### Kiro (device_code)
- AWS SSO OIDC endpoints
- Supports: Builder ID, IDC, Google/GitHub social login, Import token
- Registers client first, then requests device auth
- Stores: profileArn, clientId, clientSecret, region, authMethod, startUrl

#### Cursor (import_token)
- No OAuth flow — user imports token from Cursor IDE's SQLite DB
- Token storage: `~/.config/Cursor/User/globalStorage/state.vscdb`
- Keys: `cursorAuth/accessToken`, `storage.serviceMachineId`

#### Kilo Code (device_code)
- Initiate: `POST config.initiateUrl`
- Poll: `GET config.pollUrlBase/{code}`
- Fetches orgId from profile for `X-Kilocode-OrganizationID` header

#### Cline (authorization_code)
- Authorize: `https://app.cline.bot/api/v1/auth/authorize`
- Token exchange: decodes base64 from code param
- Falls back to API exchange if base64 decode fails

#### GitLab (authorization_code_pkce)
- Supports custom instance URL (self-hosted GitLab)
- Also supports PAT (Personal Access Token) import mode
- Fetches user info from GitLab API

#### CodeBuddy/Tencent (device_code variant)
- POST to stateUrl → get `{ state, authUrl }`
- Open authUrl in browser
- Poll tokenUrl with state until `code === 0`

#### Qwen (device_code)
- Device code URL: `https://chat.qwen.ai/api/v1/oauth2/device/code`
- Uses PKCE (code_challenge + code_verifier)
- Stores `resourceUrl` from token response

#### iFlow (authorization_code)
- Uses Basic Auth (clientId:clientSecret)
- Fetches user info → gets apiKey from response
- Stores: apiKey, email/phone, displayName

---

## 8. UI Components

### Main Page Components (`providers/page.js`)
- **Card** — Section wrapper for each provider category
- **Badge** — Status indicators (Connected, Error, etc.)
- **Toggle** — Enable/disable all connections for a provider
- **ProviderIcon** — Renders provider icon (Material icon or text fallback)
- **ModelAvailabilityBadge** — Shows model availability status

### Detail Page Components (`providers/[id]/`)

#### `ConnectionRow.js`
- Displays single connection with:
  - Name/email, status badge, priority
  - Proxy pool selector (dropdown)
  - Cooldown timer (when rate-limited)
  - Actions: toggle active, move up/down, edit, delete

#### `AddApiKeyModal.js`
- Modal for adding API key connections
- Fields: Name, API Key, Default Model, Priority, Proxy Pool
- Special handling for: Azure (endpoint, deployment, apiVersion), Cloudflare (accountId), Ollama Local (host URL), Web Cookie (cookie value)
- Bulk mode: paste multiple `name|key` entries
- Validate button → tests key before saving

#### `ModelRow.js`
- Displays single model with: ID, name, copy button, test button
- Test status indicator (ok/error/pending)
- Custom model delete option

#### `PassthroughModelsSection.js`
- For providers with `passthroughModels: true` (OpenRouter, OpenCode, etc.)
- Fetches models from provider's `/v1/models` endpoint
- Shows model list with copy/test/delete actions
- "Fetch Models" button to refresh

#### `CompatibleModelsSection.js`
- For custom OpenAI/Anthropic compatible providers
- Similar to PassthroughModelsSection but for compatible providers
- Add custom model button

#### `AddCustomModelModal.js`
- Modal to add custom model ID to a compatible provider
- Input: model ID string

#### `EditCompatibleNodeModal.js`
- Edit compatible provider node: name, prefix, baseUrl, apiType

#### `CooldownTimer.js`
- Shows remaining cooldown time when connection is rate-limited

### Shared Components
- `ProviderIcon.js` — Renders provider icon by name
- `ProviderInfoCard.js` — Provider info display card

---

## 9. State Management (Store)

### `providerStore.js` (Zustand)
```js
const useProviderStore = create((set, get) => ({
  providers: [],        // Array of provider connections
  loading: false,
  error: null,
  lastFetched: 0,       // Timestamp of last fetch

  // Actions
  setProviders: (providers) => set({ providers, lastFetched: Date.now() }),
  addProvider: (provider) => set(state => ({ providers: [provider, ...state.providers] })),
  updateProvider: (id, updates) => set(state => ({
    providers: state.providers.map(p => p._id === id ? { ...p, ...updates } : p)
  })),
  removeProvider: (id) => set(state => ({
    providers: state.providers.filter(p => p._id !== id)
  })),
  invalidate: () => set({ lastFetched: 0 }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  // Fetch with cache (CLIENT_STORE_TTL_MS)
  fetchProviders: async ({ force = false } = {}) => {
    // Skips network when cache is fresh
    // Calls GET /api/providers
    // Stores data.connections || data.providers
  },
}));
```

### Other Stores Used
- `notificationStore` — Toast notifications
- `headerSearchStore` — Global search query for filtering

---

## 10. API Endpoints

### Provider Connections
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/providers` | List all connections |
| POST | `/api/providers` | Create connection |
| GET | `/api/providers/client` | Dashboard-safe list (whitelist) |
| GET | `/api/providers/[id]` | Get single connection |
| PUT | `/api/providers/[id]` | Update connection |
| DELETE | `/api/providers/[id]` | Delete connection |
| POST | `/api/providers/[id]/test` | Test connection |
| POST | `/api/providers/[id]/test-models` | Test individual models |
| GET | `/api/providers/[id]/models` | Fetch models from provider |

### Provider Nodes (Custom Compatible)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/provider-nodes` | List all provider nodes |
| POST | `/api/provider-nodes` | Create provider node |
| PUT | `/api/provider-nodes/[id]` | Update provider node |
| DELETE | `/api/provider-nodes/[id]` | Delete provider node + connections |
| POST | `/api/provider-nodes/validate` | Validate API key against base URL |

### OAuth
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/oauth/[provider]/authorize` | Generate auth URL |
| POST | `/api/oauth/[provider]/exchange` | Exchange code for tokens |
| GET | `/api/oauth/[provider]/device-code` | Request device code |
| POST | `/api/oauth/[provider]/poll` | Poll for device code token |
| GET | `/api/oauth/[provider]/start-proxy` | Start Codex proxy (codex only) |
| GET | `/api/oauth/[provider]/poll-status` | Poll Codex proxy status |
| GET | `/api/oauth/[provider]/stop-proxy` | Stop Codex proxy |

### Batch & Validation
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/providers/test-batch` | Batch test connections |
| POST | `/api/providers/validate` | Validate API key |
| GET | `/api/providers/suggested-models` | Fetch suggested models |
| GET | `/api/providers/kilo/free-models` | Fetch Kilo Code free models |

### Models
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/models/disabled` | Get disabled model IDs |
| POST | `/api/models/disabled` | Disable models |
| DELETE | `/api/models/disabled` | Enable models |
| GET | `/api/models/alias` | Get model aliases |

---

## 11. Integration Points

### Chat / Completions
- Providers connect to `/v1/chat/completions` via the proxy layer
- Model routing: `provider_alias/model_name` format
- open-sse library handles provider translation
- Connection selection: priority-based, round-robin, or sticky

### Combos
- Combos use provider connections for multi-model routing
- References providers by ID

### Usage / Quota
- Usage tracking per connection
- Quota limits per provider
- `USAGE_SUPPORTED_PROVIDERS` list for providers with quota APIs

### Media Providers
- Separate media-providers page for TTS, STT, embedding, image, etc.
- Each media kind has its own route and endpoint config
- `MEDIA_PROVIDER_KINDS` defines the available kinds

### Settings
- Per-provider strategy overrides (fallbackStrategy, stickyRoundRobinLimit)
- Per-provider thinking mode config
- Global provider strategies

### Proxy Pools
- Connections can be assigned to proxy pools
- Proxy pool has: name, proxyUrl, noProxy, isActive
- Connection-level proxy config: connectionProxyEnabled, connectionProxyUrl, connectionNoProxy

---

## 12. Gap Analysis (apa yang belum ada di FastAPI port)

### Backend (FastAPI)
| Feature | Original (Next.js) | FastAPI Port | Status |
|---|---|---|---|
| Provider CRUD | ✅ Full | ✅ Exists | Likely needs review |
| Provider Nodes CRUD | ✅ Full | ❓ Check | May be missing |
| OAuth flows (all providers) | ✅ 14 providers | ✅ Partial | Some flows may be incomplete |
| Token refresh | ✅ Per-provider | ❓ Check | May be missing |
| Connection test | ✅ Full (per-provider logic) | ❓ Check | May be simplified |
| Batch test | ✅ Full | ❓ Check | May be missing |
| Model fetching | ✅ Per-provider parsing | ❓ Check | May be missing |
| Model disable/enable | ✅ Full | ❓ Check | May be missing |
| Model aliases | ✅ Full | ❓ Check | May be missing |
| Suggested models | ✅ Full | ❓ Check | May be missing |
| Provider validation | ✅ Per-type logic | ❓ Check | May be simplified |
| Proxy pools | ✅ Full | ❓ Check | May be missing |
| Provider strategies | ✅ Full | ❓ Check | May be missing |
| Thinking mode config | ✅ Full | ❓ Check | May be missing |
| Codex proxy server | ✅ Full | ❓ Check | Likely missing |
| Web cookie providers | ✅ Full | ❓ Check | May be missing |
| Media provider support | ✅ Full | ❓ Check | Separate system |
| Cooldown/rate-limit tracking | ✅ Full | ❓ Check | May be missing |

### Frontend (React/Tailwind)
| Feature | Original (Next.js) | FastAPI Port | Status |
|---|---|---|---|
| Main providers page | ✅ Full | ✅ Exists | Needs review |
| Provider detail page | ✅ Full | ✅ Exists | Needs review |
| Add API Key modal | ✅ Full (bulk, validate) | ❓ Check | May be simplified |
| Connection row | ✅ Full (proxy, cooldown) | ❓ Check | May be simplified |
| Passthrough models section | ✅ Full | ❓ Check | May be missing |
| Compatible models section | ✅ Full | ✅ Exists | Needs review |
| Add custom model modal | ✅ Full | ❓ Check | May be missing |
| Edit compatible node modal | ✅ Full | ✅ Exists | Needs review |
| OAuth modal | ✅ Full (all flow types) | ❓ Check | May be simplified |
| Batch test UI | ✅ Full | ❓ Check | May be missing |
| Model disable/enable UI | ✅ Full | ❓ Check | May be missing |
| Cooldown timer | ✅ Full | ❓ Check | May be missing |
| Provider strategy selector | ✅ Full | ❓ Check | May be missing |
| Search/filter | ✅ Full | ❓ Check | May be missing |
| New provider page | ✅ Full | ❓ Check | May be simplified |

### Key Differences to Watch
1. **Next.js uses App Router** (server components + API routes) vs **FastAPI + React SPA**
2. **Database**: Next.js uses local DB (SQLite?) via `@/models` / `@/lib/localDb` vs FastAPI uses PostgreSQL
3. **open-sse library**: Next.js imports from `open-sse/config/providers.js` and `open-sse/config/providerModels.js` — this handles provider translation at the SSE/completions layer. FastAPI port needs equivalent.
4. **Provider constants**: Next.js has `src/shared/constants/providers.js` (55K+ chars) — must be replicated in FastAPI
5. **OAuth services**: Next.js has individual service files per provider in `src/lib/oauth/services/` — FastAPI has `oauth_providers.py`
6. **Token refresh**: Next.js has `src/sse/services/tokenRefresh.js` — critical for OAuth providers
7. **Connection proxy**: Next.js has `src/lib/network/connectionProxy.js` and `proxyTest.js`
