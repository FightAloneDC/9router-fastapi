# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# 9Router — AI Model Proxy Router

Self-hosted OpenRouter alternative. Clients send OpenAI-compatible requests → 9Router resolves model alias to upstream provider → forwards request → returns response. Supports 50+ AI providers (OpenAI, Anthropic, Google, DeepSeek, Groq, etc.) with OAuth, API key, free tier, and web cookie auth.

**This is a faithful port from Next.js (at `_reference/`)**. When fixing bugs or adding features, ALWAYS read the original source code in `_reference/` first and replicate behavior exactly. Do not improvise unless explicitly asked.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | React 19 + Vite 8 + Tailwind CSS v4 + Zustand 5 + React Router v7 |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose HS256, 24h expiry) + bcrypt, password-only login (default "123456") |
| HTTP | httpx (backend→upstream), axios (frontend→backend) |

## Quick Start

```bash
docker compose -f docker-compose.dev.yml up --build
# Frontend: http://localhost:5173
# Backend:  http://localhost:9000/docs
# DB:       PostgreSQL on localhost:5432
```

## Architecture

```
backend/app/
├── main.py              # FastAPI app factory, lifespan, CORS, 13 routers
├── config.py            # pydantic-settings (DATABASE_URL, SECRET_KEY, etc.)
├── database.py          # AsyncSession factory, get_db() dependency
├── models/              # SQLAlchemy models (provider, user, api_key, combo, usage, etc.)
├── schemas/             # Pydantic schemas (request/response validation)
├── routers/
│   ├── auth.py          # /auth/* — login, status, me
│   ├── providers/       # ★ MODULAR: connections, models, nodes, testing, validation
│   ├── v1_proxy.py      # ★ POST /v1/chat/completions — core proxy (streaming + non-streaming)
│   ├── oauth.py         # OAuth flows (PKCE, device code, Codex, Cursor, GitHub, etc.)
│   └── ...              # combos, usage, quota, mitm, cli_tools, proxy_pools, settings, console
├── services/
│   ├── proxy.py         # ★★ Model→provider resolution, upstream URL/header construction
│   ├── auth.py          # bcrypt + JWT
│   ├── oauth.py         # PKCE utilities, OAuth handlers (1800+ lines)
│   └── oauth_providers.py # OAuth config per provider (1400+ lines)
└── utils/pkce.py        # PKCE helper

frontend/src/
├── App.jsx              # Routes (16 pages), all dashboard routes wrapped in ProtectedRoute
├── api/                 # Axios API modules (providers.js has 40+ methods)
├── constants/
│   └── providers.js     # ★ Provider definitions, ALIAS_TO_ID, ID_TO_ALIAS
├── pages/
│   ├── ProvidersPage.jsx      # ★ Provider list (1050 lines)
│   ├── ProviderDetailPage.jsx # ★ Provider detail (2179 lines — jantung project)
│   └── ...                    # 14 other pages
├── components/          # UI components + modals
├── stores/              # Zustand stores (authStore, notificationStore)
└── utils/               # Helpers
```

## Critical Patterns (MUST KNOW)

### 1. Provider Data = JSON Blob
All provider-specific data stored in a single `data` JSON TEXT column, NOT separate DB columns:
```json
{"apiKey": "...", "models": ["gpt-4"], "baseUrl": "https://...", "testStatus": "connected"}
```
**NEVER add new columns to provider tables** — put everything in the JSON blob.

### 2. Constants Duplication (Backend + Frontend)
Provider config (URLs, auth headers, validation types) exists in TWO places:
- **Backend**: `routers/providers/constants.py` (DEFAULTS), `services/proxy.py` (PROVIDER_CONFIGS, ALIAS_TO_ID)
- **Frontend**: `constants/providers.js` (ALIAS_TO_ID, ID_TO_ALIAS, provider definitions)
- **ALWAYS sync both sides** when adding/changing providers.

### 3. Alias System
Model strings use 2-5 char aliases: `"an/claude-sonnet-4"` → alias "an" → provider "anthropic"
- Backend: `services/proxy.py` → `ALIAS_TO_ID` (82 entries)
- Frontend: `constants/providers.js` → `ALIAS_TO_ID`, `ID_TO_ALIAS`

### 4. Provider Categories
| Category | Auth | Examples |
|----------|------|----------|
| Free | None | kiro, qwen, opencode |
| Free Tier | Free API key | openrouter, nvidia, gemini |
| OAuth | OAuth flow | claude, codex, github, cursor |
| API Key | User's API key | ~40 providers (openai, anthropic, deepseek, groq) |
| Web Cookie | Browser cookie | grok-web, perplexity-web |
| Custom | Custom endpoint | OpenAI/Anthropic-compatible nodes |

### 5. Sensitive Data Stripping
`apiKey`, `accessToken`, `refreshToken`, `idToken` are stripped from `/providers/client` responses.

### 6. Provider Node Cascade
Deleting a node auto-deletes all connections referencing it.

## Key Files to Read First

When working on a bug or feature, trace the full round-trip:

### Backend
1. `backend/app/main.py` — See all 13 routers
2. `backend/app/routers/providers/connections.py` — Provider CRUD (422 lines, most complex)
3. `backend/app/services/proxy.py` — Core proxy routing (531 lines)
4. `backend/app/routers/v1_proxy.py` — Proxy endpoint (270 lines)
5. `backend/app/routers/providers/models.py` — Model fetching/clearing (563 lines)
6. `backend/app/routers/providers/nodes.py` — Node CRUD + validation (391 lines)
7. `backend/app/models/provider.py` — ProviderConnection + ProviderNode models
8. `backend/app/schemas/provider.py` — All Pydantic schemas (227 lines)
9. `backend/app/services/oauth.py` — OAuth service (1818 lines)
10. `backend/app/services/oauth_providers.py` — OAuth configs per provider (1390 lines)

### Frontend
1. `frontend/src/App.jsx` — Routing (70 lines)
2. `frontend/src/api/providers.js` — API calls (68 lines, 40+ methods)
3. `frontend/src/constants/providers.js` — Provider definitions (171 lines)
4. `frontend/src/pages/ProvidersPage.jsx` — Provider list page (1050 lines)
5. `frontend/src/pages/ProviderDetailPage.jsx` — Provider detail page (2179 lines)
6. `frontend/src/stores/authStore.js` — Auth state management

### Reference (Original Next.js)
- `_reference/providers.js` — Original providers page (52KB)
- `_reference/components/` — Original component implementations
- `_reference/lib/`, `_reference/store/`, `_reference/shared/` — Original utilities

## Debugging Workflows

### Provider connection not showing in UI
```
1. docker compose -f docker-compose.dev.yml logs backend
2. curl http://localhost:9000/providers/client -H "Authorization: Bearer $TOKEN"
3. Check snake_case vs camelCase field names
4. Check ProvidersPage.jsx: setConnections(connRes.data?.connections || connRes.data || [])
5. Check api/client.js: is 401 interceptor firing incorrectly?
```

### Test connection fails
```
1. POST /providers/{id}/test → check response
2. Check console log viewer (WS /console/ws)
3. Check constants.py: is validationType correct?
4. Check validation.py: can server reach the upstream endpoint?
```

### Fetch models not working
```
1. GET /providers/{conn_id}/models
2. Check PROVIDER_MODELS_CONFIG in models.py — does provider have entry?
3. Check auth header: Bearer vs x-api-key vs query param
4. Is it node-based (compatible) or built-in provider?
```

### OAuth flow stuck
```
1. Verify redirect URI matches what's registered with provider
2. Check callback endpoint receives code correctly
3. Check token exchange: is client_id/secret valid?
4. Codex: check local proxy server on port 1455
```

## Common Commands

```bash
# Start dev environment
docker compose -f docker-compose.dev.yml up --build

# Run backend migrations
docker compose -f docker-compose.dev.yml exec backend uv run alembic upgrade head

# Create new migration
docker compose -f docker-compose.dev.yml exec backend uv run alembic revision --autogenerate -m "description"

# Quick auth token
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
```

## Rules for AI Agents

1. **READ BEFORE WRITE** — Always read the original Next.js source in `_reference/` before implementing. User expects faithful porting, not redesign.
2. **No new DB columns** — Provider data goes in the JSON `data` blob.
3. **Sync constants** — Backend + Frontend provider configs must stay in sync.
4. **ProviderDetailPage is the heart** — ALL features in the Providers menu must be fully fixed and working.
5. **No half-measures** — Verify fixes in the running app, not just in code. If user says something is broken, they're right.
6. **Optimistic updates** — Toggle UI state first, then API call. Rollback on failure.
7. **Docker auto-reloads** — Backend and frontend have volume mounts + hot reload. Don't rebuild containers for code changes.
