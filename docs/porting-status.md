# 9Router FastAPI — Porting Status & Gap Analysis

**Original project:** `~/dev/9router/` (Next.js 14, App Router)
**Port project:** `~/dev/9router-fastapi/` (FastAPI + React 19 + Vite)
**Last updated:** 2026-05-23
**Investigated by:** Kiro (Hermes Agent)

---

## Overview

9Router is a self-hosted OpenRouter alternative. Clients send OpenAI-compatible
requests → 9Router resolves model alias to upstream provider → forwards request
→ returns response. Supports 50+ AI providers with OAuth, API key, free tier,
and web cookie auth.

The FastAPI port replaces the Next.js backend (API routes) with Python FastAPI,
and replaces the Next.js frontend (React Server Components) with a standalone
React 19 + Vite SPA. The core proxy logic, provider system, and dashboard UI
have all been ported.

---

## Stack Comparison

| Layer        | Original (Next.js)                          | Port (FastAPI)                              |
|--------------|---------------------------------------------|---------------------------------------------|
| Backend      | Next.js API routes (Node.js)                | Python 3.12 + FastAPI + SQLAlchemy (async)  |
| Frontend     | Next.js React Server Components             | React 19 + Vite 8 + Tailwind CSS v4         |
| State        | Zustand + React Query                       | Zustand 5                                   |
| Database     | SQLite (via localDb.js / better-sqlite3)    | PostgreSQL 16 (Docker)                      |
| Auth         | bcrypt + JWT (Next.js session)              | JWT HS256 (python-jose) + bcrypt, 24h expiry|
| HTTP client  | fetch (native)                              | httpx (backend), axios (frontend)           |
| Migrations   | None (SQLite file)                          | Alembic                                     |

---

## Architecture: FastAPI Port

```
backend/app/
├── main.py                    # App factory, lifespan, CORS, 14 routers
├── config.py                  # pydantic-settings
├── database.py                # AsyncSession factory
├── models/                    # SQLAlchemy ORM models
├── schemas/                   # Pydantic request/response schemas
├── routers/
│   ├── auth.py                # POST /auth/login, /auth/status, /auth/me
│   ├── providers/             # Modular: connections, models, nodes, testing, validation
│   │   ├── connections.py     # Provider CRUD (436 lines)
│   │   ├── models.py          # Model fetch/clear/type-change (563 lines)
│   │   ├── nodes.py           # Custom node CRUD + validation (391 lines)
│   │   ├── testing.py         # Test connection + batch test
│   │   ├── validation.py      # Pre-save validation per provider type
│   │   └── constants.py       # PROVIDER_DEFAULTS (base URLs, validationTypes)
│   ├── v1_proxy.py            # POST /v1/chat/completions, GET /v1/models
│   ├── oauth.py               # OAuth flows (29.7KB — Kiro, Cursor, GitHub, etc.)
│   ├── media_providers.py     # GET /media-providers/{kind}
│   ├── models.py              # /models/alias, /models/custom, /models/disabled, etc.
│   ├── combos.py              # Combo CRUD
│   ├── usage.py               # Usage stats, logs, charts
│   ├── quota.py               # Quota tracking
│   ├── settings.py            # App settings
│   ├── mitm.py                # MITM proxy
│   ├── cli_tools.py           # CLI tool configs
│   ├── proxy_pools.py         # Proxy pool CRUD
│   ├── console.py             # WebSocket console log buffer
│   └── api_keys.py            # API key management
├── services/
│   ├── proxy.py               # ★★ Core: model→provider resolution, upstream routing (574 lines)
│   ├── auth.py                # bcrypt + JWT
│   ├── oauth.py               # OAuth handlers (1818 lines)
│   ├── oauth_providers.py     # OAuth config per provider (1390 lines)
│   └── token_refresh.py       # Background token refresh loop

frontend/src/
├── App.jsx                    # 19 routes
├── api/providers.js           # 40+ API methods (axios)
├── constants/
│   ├── providers.js           # Provider definitions, ALIAS_TO_ID, serviceKinds (173 lines)
│   └── navigation.js          # Nav items, pageTitles, mediaProviderKinds
├── pages/
│   ├── ProvidersPage.jsx      # LLM provider list (1061 lines / 44KB)
│   ├── ProviderDetailPage.jsx # Provider detail — "jantung" (2287 lines / 98KB)
│   ├── MediaProvidersPage.jsx # Media provider list by kind (284 lines)
│   ├── MediaProviderDetailPage.jsx  # Media provider detail (17KB)
│   └── ... 15 other pages
└── components/                # UI components, modals, OAuthModal, etc.
```

---

## Critical Patterns (Must Know)

### 1. Provider Data = JSON Blob
All provider-specific data stored in a single `data` TEXT column, NOT separate
DB columns. Never add new columns to provider tables.

```json
{"apiKey": "...", "models": ["gpt-4"], "baseUrl": "https://...", "testStatus": "connected"}
```

### 2. Constants Must Stay in Sync (Both Sides)
Provider config exists in TWO places — always update both:
- **Backend:** `routers/providers/constants.py` → `PROVIDER_DEFAULTS`
- **Backend:** `services/proxy.py` → `ALIAS_TO_ID` (84 entries)
- **Frontend:** `constants/providers.js` → `AI_PROVIDERS`, `ALIAS_TO_ID`, `ID_TO_ALIAS`

### 3. Alias System
Model strings use 2-5 char aliases: `"an/claude-sonnet-4"` → alias `"an"` → provider `"anthropic"`.
- Backend resolves in `services/proxy.py → _resolve_provider_alias()`
- Frontend resolves in `constants/providers.js → getProviderByAlias()`

### 4. Provider Categories
| Category     | Auth         | Examples                                    |
|--------------|--------------|---------------------------------------------|
| Free         | None/OAuth   | kiro, qwen, gemini-cli, opencode            |
| Free Tier    | Free API key | openrouter, nvidia, gemini, cloudflare-ai   |
| OAuth        | OAuth flow   | claude, codex, github, cursor, kilocode     |
| API Key      | User API key | openai, anthropic, deepseek, groq, ~40 more |
| Web Cookie   | Browser cookie | grok-web, perplexity-web                  |
| Custom       | Custom endpoint | openai-compatible-*, anthropic-compatible-* |

### 5. Sensitive Data Stripping
`apiKey`, `accessToken`, `refreshToken`, `idToken` are stripped from
`/providers/client` responses via `_sanitize_connection()` in helpers.py.

### 6. serviceKinds
Each provider declares which service types it supports. Default is `["llm"]`.
Used to filter providers in `/providers?kind=embedding` and MediaProvidersPage.
Must be declared in BOTH `constants/providers.js` AND `routers/providers/constants.py`.

---

## Reference Directory

`_reference/` in the FastAPI project contains selected files copied from the
original for reference during porting:

```
_reference/
├── providers.js               # Original providers page (52KB) — use when fixing ProvidersPage
├── AddApiKeyModal.js          # Original add API key modal
├── components/
│   ├── ConnectionRow.js       # Original connection row component
│   ├── ConnectionsCard.js     # Original connections card (23.9KB)
│   ├── ModelsCard.js          # Original models card (12.7KB)
│   └── provider-page.js       # Original provider detail page
├── app/
│   ├── models-route.js        # Original /api/providers/[id]/models route (17.3KB)
│   ├── suggested-models-route.js
│   ├── test-models-route.js
│   └── test-route.js
├── lib/
│   ├── providerModelsFetcher.js
│   └── providerNormalization.js
└── shared/constants/
    └── providers.js           # Original provider constants (52.2KB)
```

**Rule:** Always read `_reference/` before implementing or fixing anything in
the providers area. The port must be faithful to the original behavior.

---

## Porting Status

### ✅ Fully Ported

| Feature                        | Original                              | FastAPI                                    |
|-------------------------------|---------------------------------------|--------------------------------------------|
| Auth (login/logout/status)    | `/api/auth/*`                         | `routers/auth.py`                          |
| Provider CRUD                 | `/api/providers/route.js`             | `routers/providers/connections.py`         |
| Provider test                 | `/api/providers/[id]/test`            | `routers/providers/testing.py`             |
| Provider models fetch/clear   | `/api/providers/[id]/models`          | `routers/providers/models.py`              |
| Provider nodes (custom compat)| `/api/provider-nodes`                 | `routers/providers/nodes.py`               |
| Provider validation           | `/api/providers/validate`             | `routers/providers/validation.py`          |
| Suggested models              | `/api/providers/suggested-models`     | `routers/providers/connections.py`         |
| v1/chat/completions proxy     | `/api/v1/chat/completions`            | `routers/v1_proxy.py`                      |
| v1/embeddings proxy           | `/api/v1/embeddings`                  | `routers/v1_proxy.py`                      |
| v1/models list                | `/api/v1/models`                      | `routers/v1_proxy.py`                      |
| OAuth flows                   | `/api/oauth/[provider]/[action]`      | `routers/oauth.py` (29.7KB)                |
| Model aliases                 | `/api/models/alias`                   | `routers/models.py`                        |
| Custom models                 | `/api/models/custom`                  | `routers/models.py`                        |
| Disabled models               | `/api/models/disabled`                | `routers/models.py`                        |
| Model availability/cooldown   | `/api/models/availability`            | `routers/models.py`                        |
| Combos                        | `/api/combos`                         | `routers/combos.py`                        |
| Usage stats/logs/charts       | `/api/usage/*`                        | `routers/usage.py`                         |
| Quota tracker                 | `/api/quota` (implied)                | `routers/quota.py`                         |
| Settings (GET/PATCH)          | `/api/settings`                       | `routers/settings.py`                      |
| MITM proxy                    | `/api/mitm` (implied)                 | `routers/mitm.py`                          |
| CLI tools                     | `/api/cli-tools/*`                    | `routers/cli_tools.py`                     |
| Proxy pools                   | `/api/proxy-pools`                    | `routers/proxy_pools.py`                   |
| Console log (WebSocket)       | (console log buffer)                  | `routers/console.py`                       |
| API keys                      | `/api/keys`                           | `routers/api_keys.py`                      |
| Media providers list          | `/api/media-providers/tts` (partial)  | `routers/media_providers.py`               |
| Background token refresh      | (cron-like in Node)                   | `services/token_refresh.py`                |

### ❌ Not Yet Ported

#### v1 Proxy Endpoints (High Priority)
The original supports a full OpenAI-compatible API surface. The FastAPI port
only has `/v1/chat/completions` and `/v1/models`. Missing:

| Endpoint                        | Original file                              | Notes                                      |
|---------------------------------|--------------------------------------------|--------------------------------------------|
| `POST /v1/audio/transcriptions` | `api/v1/audio/transcriptions/route.js`     | STT proxy                                  |
| `GET /v1/audio/voices`          | `api/v1/audio/voices/route.js`             | List TTS voices                            |
| `POST /v1/images/generations`   | `api/v1/images/generations/route.js`       | Image generation proxy                     |
| `POST /v1/search`               | `api/v1/search/route.js`                   | Web search proxy                           |
| `POST /v1/web/fetch`            | `api/v1/web/fetch/route.js`                | Web fetch proxy                            |
| `POST /v1/messages`             | `api/v1/messages/route.js`                 | Anthropic-format messages proxy            |
| `POST /v1/responses`            | `api/v1/responses/route.js`                | OpenAI responses API proxy                 |
| `GET /v1/models/{kind}`         | `api/v1/models/[kind]/route.js`            | Models filtered by kind                    |
| `GET /v1/models/info`           | `api/v1/models/info/route.js`              | Model info endpoint                        |

### 🔧 In Progress

| Endpoint                        | FastAPI path                          | Status                                                                                                  |
|---------------------------------|---------------------------------------|---------------------------------------------------------------------------------------------------------|
| `POST /v1/audio/speech`         | `/api/v1/audio/speech` (routers/v1_proxy.py) | 🟢 Iterasi 2 done (2026-05-23): 8 TTS adapters wired (openai, siliconflow, hyperbolic, gemini, elevenlabs, minimax, minimax-cn, openrouter). Gemini live-tested — returns valid 24kHz mono WAV. Iterasi 3 pending: nvidia, deepgram, huggingface, inworld, cartesia, playht. Group C (local TTS servers) deferred. See `docs/plans/v1-audio-speech.md`. |

#### Dashboard Pages (Medium Priority)
| Page              | Original path                                          | Status in FastAPI port         |
|-------------------|--------------------------------------------------------|--------------------------------|
| Basic Chat        | `(dashboard)/dashboard/basic-chat/`                    | Not ported (no page exists)    |
| Profile           | `(dashboard)/dashboard/profile/`                       | Not ported                     |
| Translator        | `(dashboard)/dashboard/translator/`                    | Not ported                     |
| Combos            | `(dashboard)/dashboard/combos/`                        | Page exists (CombosPage.jsx)   |

#### Backend Features (Medium Priority)
| Feature                        | Original                                  | Notes                                      |
|-------------------------------|-------------------------------------------|--------------------------------------------|
| Tunnel (Tailscale)            | `/api/tunnel/*` (12 endpoints)            | Not ported — system-level feature          |
| Translator                    | `/api/translator/*` (5 endpoints)         | Not ported                                 |
| MCP server                    | `/api/mcp/[plugin]/sse` + `/message`      | Not ported                                 |
| Tags                          | `/api/tags`                               | Not ported                                 |
| Pricing                       | `/api/pricing`                            | Not ported                                 |
| OIDC auth                     | `/api/auth/oidc/*`                        | Not ported (FastAPI only has password auth)|
| App version/update            | `/api/version/*`                          | Not ported                                 |
| Shutdown endpoint             | `/api/shutdown`                           | Not ported                                 |
| `/providers/kilo/free-models` | `/api/providers/kilo/free-models`         | Not ported                                 |
| `/providers/[id]/test-models` | `/api/providers/[id]/test-models`         | Not ported                                 |
| Settings sub-endpoints        | `/api/settings/database`, `/proxy-test`   | Only GET/PATCH settings ported             |
| Proxy pools Vercel deploy     | `/api/proxy-pools/vercel-deploy`          | Not ported                                 |

#### Media Provider Voices (Low Priority)
| Feature                        | Original                                          | Notes                          |
|-------------------------------|---------------------------------------------------|--------------------------------|
| TTS voices list               | `/api/media-providers/tts/voices`                 | Not ported                     |
| ElevenLabs voices             | `/api/media-providers/tts/elevenlabs/voices`      | Not ported                     |
| Deepgram voices               | `/api/media-providers/tts/deepgram/voices`        | Not ported                     |
| Minimax voices                | `/api/media-providers/tts/minimax/voices`         | Not ported                     |
| Inworld voices                | `/api/media-providers/tts/inworld/voices`         | Not ported                     |

---

## Known Issues & Quirks

### Provider System
- `ProviderDetailPage.jsx` is 2287 lines / 98KB — the most complex file in the project.
  Piecemeal edits cause conflicts. Always spec-first before touching it.
- Badge.jsx: `dot` prop must be a string, not a boolean.
- When clearing models: use `DELETE /providers/{conn_id}/models`, NOT `PATCH` with `{models: []}`.
- `serviceKinds` must be declared in BOTH frontend `constants/providers.js` AND
  backend `routers/providers/constants.py` — they are not auto-synced.

### Config / Settings
- `hermes config set` converts dicts to JSON strings — code reads dict, ignores strings.
  Patch YAML directly for nested values.
- Docker Compose: always use `docker-compose.dev.yml` with `-f` flag explicitly.
  `docker-compose.example.yml` is the prod template.
- Backend and frontend have volume mounts + hot reload. No rebuild needed for code changes.

### Auth
- Default admin password: `123456`
- Auth endpoint: `POST /auth/login` with `{"password": "123456"}`
- JWT expiry: 24 hours

### Database
- Local Docker PostgreSQL 16 on port 5432
- All provider-specific data in `data` TEXT column (JSON blob)
- Never add new columns to provider tables

---

## Quick Reference: Common Commands

```bash
# Start dev environment
docker compose -f docker-compose.dev.yml up --build

# Run backend migrations
docker compose -f docker-compose.dev.yml exec backend uv run alembic upgrade head

# Create new migration
docker compose -f docker-compose.dev.yml exec backend uv run alembic revision --autogenerate -m "description"

# Get auth token
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')

# List providers
curl http://localhost:9000/providers/client -H "Authorization: Bearer $TOKEN"

# Test proxy
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}'

# View API docs
open http://localhost:9000/docs

# Frontend
open http://localhost:5173
```

---

## File Size Reference (Key Files)

| File                                                              | Lines | Size   |
|-------------------------------------------------------------------|-------|--------|
| `frontend/src/pages/ProviderDetailPage.jsx`                       | 2287  | 98KB   |
| `backend/app/services/oauth.py`                                   | 1818  | ~70KB  |
| `backend/app/services/oauth_providers.py`                         | 1390  | ~55KB  |
| `frontend/src/pages/ProvidersPage.jsx`                            | 1061  | 44KB   |
| `backend/app/routers/providers/models.py`                         | 563   | 25.7KB |
| `backend/app/routers/providers/connections.py`                    | 436   | 15.1KB |
| `backend/app/routers/providers/constants.py`                      | 260   | 14.7KB |
| `backend/app/routers/v1_proxy.py`                                 | ~270  | 12.0KB |
| `backend/app/routers/oauth.py`                                    | ~900  | 29.7KB |
| `frontend/src/pages/MediaProviderDetailPage.jsx`                  | ~600  | 17.1KB |
| `frontend/src/constants/providers.js`                             | 173   | 22KB   |
| `backend/app/services/proxy.py`                                   | 574   | 19.4KB |

---

## Debugging Workflows

### Provider connection not showing in UI
1. `docker compose -f docker-compose.dev.yml logs backend`
2. `curl http://localhost:9000/providers/client -H "Authorization: Bearer $TOKEN"`
3. Check snake_case vs camelCase field names
4. Check `ProvidersPage.jsx`: `setConnections(connRes.data?.connections || connRes.data || [])`

### Test connection fails
1. `POST /providers/{id}/test` → check response
2. Check console log viewer (WS `/console/ws`)
3. Check `constants.py`: is `validationType` correct?
4. Check `validation.py`: can server reach the upstream endpoint?

### Fetch models not working
1. `GET /providers/{conn_id}/models`
2. Check `PROVIDER_MODELS_CONFIG` in `models.py` — does provider have entry?
3. Check auth header: Bearer vs x-api-key vs query param
4. Is it node-based (compatible) or built-in provider?

### OAuth flow stuck
1. Verify redirect URI matches what's registered with provider
2. Check callback endpoint receives code correctly
3. Check token exchange: is client_id/secret valid?
4. Codex: check local proxy server on port 1455

---

## Priority Recommendations

**High** — v1 proxy endpoints (TTS, STT, embeddings, images, search, web fetch).
These are what make 9Router a full proxy router, not just an LLM forwarder.
The original `services/proxy.py` already has provider resolution logic that can
be extended. Each endpoint follows the same pattern as chat/completions.

**Medium** — Basic Chat page. The original has a built-in chat UI for testing
providers directly. Useful for QA without needing an external client.

**Medium** — OIDC auth. The original supports OIDC for enterprise SSO.
Currently the FastAPI port only has password auth.

**Low** — Tunnel, Translator, MCP, Tags, Pricing. These are auxiliary features
that don't affect core proxy functionality.
