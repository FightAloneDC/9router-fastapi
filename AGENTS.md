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

## 5. Language Rules (MANDATORY)

- **Code and documentation: ALWAYS English.** Every file, skill, config, comment, variable name, function name, doc, README — English only. No exceptions.
- **Communication with user: ALWAYS Indonesian.** All conversation, explanations, questions, and responses in Bahasa Indonesia.
- **This rule has been stated hundreds of times. Do not forget. Do not violate.**

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# 9Router — AI Model Proxy Router

Self-hosted OpenRouter alternative. Clients send OpenAI-compatible requests → 9Router resolves model alias to upstream provider → forwards request → returns response. Supports 90+ AI providers (OpenAI, Anthropic, Google, DeepSeek, Groq, Qoder, etc.) with OAuth, API key, free tier, and web cookie auth.

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
├── main.py              # FastAPI app factory, lifespan, CORS
├── config.py            # pydantic-settings (DATABASE_URL, SECRET_KEY, etc.)
├── database.py          # AsyncSession factory, get_db() dependency
├── models/              # SQLAlchemy models (provider, user, api_key, combo, usage, etc.)
├── schemas/             # Pydantic schemas (request/response validation)
├── routers/
│   ├── auth.py          # /auth/* — login, status, me
│   ├── providers/       # ★ MODULAR: connections, models, nodes, testing, validation, catalog
│   ├── v1_proxy/        # ★ MODULAR: chat.py, messages.py, responses.py, embeddings.py, etc.
│   ├── oauth.py         # OAuth flows (PKCE, device code, Codex, Cursor, GitHub, etc.)
│   └── ...              # combos, usage, quota, mitm, cli_tools, proxy_pools, settings, console
├── services/
│   ├── proxy.py         # ★★ Model→provider resolution, upstream URL/header construction
│   ├── auth.py          # bcrypt + JWT
│   ├── oauth.py         # PKCE utilities, OAuth handlers
│   ├── oauth_providers.py # OAuth config per provider
│   ├── catalog.py       # Provider catalog collector (serves metadata to frontend)
│   └── token_refresh.py # Background token refresh (OAuth + Qoder)
└── utils/               # pkce.py, helpers

backend/app/providers/   # ★★ MODULAR PROVIDER SYSTEM (PS architecture)
├── __init__.py          # AVAILABLE_PROVIDERS, PROVIDER_X constants (90+ providers)
├── base.py              # BaseProviderConfig + BaseMetadata + BaseProviderHandler
├── provider.py          # Provider class — unified accessor
├── oauth_base.py        # BaseOAuthHandler → AuthCodeHandler, DeviceCodeHandler, ImportTokenHandler
└── <provider>/          # Each provider has its own module
    ├── config.py        # ProviderConfig + ProviderMetadata
    ├── handler.py       # ProviderHandler (validate, build_request, fetch_models)
    ├── constants.py     # Provider-specific constants
    ├── auth.py          # Auth helpers (if needed)
    ├── models.py        # Model fetching/parsing
    └── oauth.py         # OAuth handler (if OAuth provider)

frontend/src/
├── App.jsx              # Routes, fetches catalog on mount
├── api/                 # Axios API modules (providers.js has 40+ methods)
├── constants/           # cliTools.js, mitmTools.js, navigation.js, skills.js
├── pages/
│   ├── ProvidersPage.jsx      # ★ Provider list (uses catalogStore)
│   ├── ProviderDetailPage.jsx # ★ Provider detail (uses catalogStore)
│   └── ...                    # 14 other pages
├── components/          # UI components + modals (OAuthModal uses catalogStore)
├── stores/              # Zustand stores (authStore, catalogStore, notificationStore)
└── utils/               # Helpers

docs/
├── archives/            # Archived docs (completed plans, audits, QA reports)
│   ├── agent-instructions/
│   ├── completed-plans/
│   ├── investigations/
│   ├── porting/
│   ├── provider-audits/
│   └── qa-reports/
├── plans/               # Active plans
│   └── frontend-compliance/BACKEND-DRIVEN-PROVIDERS.md
├── qoder/               # Qoder provider documentation
└── reference/           # Reference docs (combo system, etc.)
```

## Critical Patterns (MUST KNOW)

### 1. Provider Data = JSON Blob
All provider-specific data stored in a single `data` JSON TEXT column, NOT separate DB columns:
```json
{"apiKey": "***", "models": ["gpt-4"], "baseUrl": "https://...", "testStatus": "connected"}
```
**NEVER add new columns to provider tables** — put everything in the JSON blob.

### 2. PS Architecture (Provider-Specific)
All provider-specific logic MUST live in `backend/app/providers/<provider>/`. This is the **PS Rule**.
- **Backend**: Each provider has its own module (config, handler, constants, auth, models, oauth)
- **Frontend**: Fetches provider metadata from `/providers/catalog` endpoint via `catalogStore`
- **NEVER hardcode provider-specific logic in routers, services, or frontend**

### 3. Provider Catalog System
Frontend gets all provider metadata from backend via `/providers/catalog`:
- **Backend**: `services/catalog.py` collects metadata from all provider configs
- **Frontend**: `stores/catalogStore.js` fetches and caches catalog
- **No more hardcoded constants**: `constants/providers.js` is replaced by catalogStore
- Categories (free, oauth, apiKey, etc.) derived from backend config, not frontend lists

### 4. Alias System
Model strings use 2-5 char aliases: `"an/claude-sonnet-4"` → alias "an" → provider "anthropic"
- Backend: `services/proxy.py` → `ALIAS_TO_ID` (90+ entries)
- Frontend: Derived from catalog (not hardcoded)

### 5. Provider Categories
| Category | Auth | Examples |
|----------|------|----------|
| Free | None | kiro, qwen, opencode |
| Free Tier | Free API key | openrouter, nvidia, gemini |
| OAuth | OAuth flow | claude, codex, github, cursor, qoder |
| API Key | User's API key | ~50 providers (openai, anthropic, deepseek, groq) |
| Web Cookie | Browser cookie | grok-web, perplexity-web |
| Custom | Custom endpoint | OpenAI/Anthropic-compatible nodes |

### 6. Sensitive Data Stripping
`apiKey`, `accessToken`, `refreshToken`, `idToken` are stripped from `/providers/client` responses.

### 7. Provider Node Cascade
Deleting a node auto-deletes all connections referencing it.

### 8. Token Refresh
- **OAuth tokens**: Background refresh via `token_refresh.py`
- **Qoder tokens**: Dual refresh — on-demand (401/403 retry) + background (every 5 min)
- **API keys**: No refresh needed (user provides)

## Key Files to Read First

When working on a bug or feature, trace the full round-trip:

### Backend
1. `backend/app/main.py` — See all routers
2. `backend/app/routers/providers/connections.py` — Provider CRUD (most complex)
3. `backend/app/services/proxy.py` — Core proxy routing
4. `backend/app/routers/v1_proxy/` — Proxy endpoints (chat.py, messages.py, responses.py)
5. `backend/app/routers/providers/models.py` — Model fetching/clearing
6. `backend/app/routers/providers/nodes.py` — Node CRUD + validation
7. `backend/app/routers/providers/catalog.py` — Provider catalog endpoint
8. `backend/app/models/provider.py` — ProviderConnection + ProviderNode models
9. `backend/app/schemas/provider.py` — All Pydantic schemas
10. `backend/app/services/catalog.py` — Catalog collector
11. `backend/app/services/oauth.py` — OAuth service
12. `backend/app/services/token_refresh.py` — Token refresh (OAuth + Qoder)

### Frontend
1. `frontend/src/App.jsx` — Routing, catalog fetch on mount
2. `frontend/src/api/providers.js` — API calls (40+ methods)
3. `frontend/src/stores/catalogStore.js` — Provider metadata from backend
4. `frontend/src/pages/ProvidersPage.jsx` — Provider list page
5. `frontend/src/pages/ProviderDetailPage.jsx` — Provider detail page
6. `frontend/src/components/OAuthModal.jsx` — OAuth modal (uses catalogStore)
7. `frontend/src/stores/authStore.js` — Auth state management

### Provider Module (when adding/modifying providers)
1. `backend/app/providers/<provider>/config.py` — Config + Metadata
2. `backend/app/providers/<provider>/handler.py` — Request building, validation
3. `backend/app/providers/<provider>/constants.py` — Provider-specific constants
4. `backend/app/providers/<provider>/oauth.py` — OAuth handler (if applicable)
5. `backend/app/providers/base.py` — Base classes (BaseProviderConfig, BaseMetadata, BaseProviderHandler)

### Reference (Original Next.js)
- `_reference/providers.js` — Original providers page (52KB)
- `_reference/components/` — Original component implementations
- `_reference/lib/`, `_reference/store/`, `_reference/shared/` — Original utilities

## Debugging Workflows

### Provider connection not showing in UI
```
1. docker compose -f docker-compose.dev.yml logs backend
2. curl http://localhost:9000/providers/client -H "Authorization: Bearer ***"
3. Check snake_case vs camelCase field names
4. Check ProvidersPage.jsx: uses catalogStore, not hardcoded constants
5. Check catalogStore: is catalog loaded? (useCatalogStore.getState().loaded)
```

### Test connection fails
```
1. POST /providers/{id}/test → check response
2. Check console log viewer (WS /console/ws)
3. Check provider handler: is validationType correct?
4. Check provider constants: can server reach the upstream endpoint?
```

### Fetch models not working
```
1. GET /providers/{conn_id}/models
2. Check provider handler: does provider have fetch_models()?
3. Check auth header: Bearer vs x-api-key vs query param
4. Is it node-based (compatible) or built-in provider?
```

### OAuth flow stuck
```
1. Verify redirect URI matches what's registered with provider
2. Check callback endpoint receives code correctly
3. Check token exchange: is client_id/secret valid?
4. Codex: check local proxy server on port 1455
5. Qoder: check device code flow + PAT import support
```

### Token expired (Qoder)
```
1. Check background refresh: docker compose logs backend | grep refresh
2. Check on-demand refresh: proxy should catch 401/403 and retry
3. Check refresh token: is it still valid? (48h expiry)
4. If refresh expired: user needs to re-import PAT
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

# Get provider catalog
curl http://localhost:9000/providers/catalog -H "Authorization: Bearer $TOKEN"

# Test proxy
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}'

# View API docs
open http://localhost:9000/docs

# Run tests locally (use .venv-local, NOT .venv)
cd backend && ../.venv-local/bin/pytest tests/ -v
```

## Rules for AI Agents

1. **READ BEFORE WRITE** — Always read the original Next.js source in `_reference/` before implementing. User expects faithful porting, not redesign.
2. **No new DB columns** — Provider data goes in the JSON `data` blob.
3. **PS Rule** — All provider-specific logic MUST live in `backend/app/providers/<provider>/`. No hardcoded provider checks in routers or frontend.
4. **ProviderDetailPage is the heart** — ALL features in the Providers menu must be fully fixed and working.
5. **No half-measures** — Verify fixes in the running app, not just in code. If user says something is broken, they're right.
6. **Optimistic updates** — Toggle UI state first, then API call. Rollback on failure.
7. **Docker auto-reloads** — Backend and frontend have volume mounts + hot reload. Don't rebuild containers for code changes.
8. **Use catalogStore** — Frontend gets provider metadata from backend via `/providers/catalog`. Don't hardcode provider lists.
9. **Respect backup files** — Files with `-v*` suffix are intentional backups in `.gitignore`. Don't delete or modify them.
10. **Docs in English** — All documentation and code comments must be in English. Use chat language (Indonesian) for user communication.

---

## Global Rules

- Do not auto-commit, push, or tag without explicit permission
- Do not delete files without asking first
- Ask before judging existing configuration as broken
- Do not expand scope beyond the specified focus
- Report outcomes, do not claim success before testing
- Prefer reading existing code before making changes
- If file exceeds 200-300 lines, split or make modular
- Never write test artifacts, scratch files, or temporary scripts to `/tmp`. Use a `tests/` folder inside the current workdir. The host has 1+ month uptime — `/tmp` does not auto-clean.

## Python Rules (Backend — FastAPI)

- Use venv in project workdir, never system-wide
- Type annotations required for all function parameters and return values
- Prefer stdlib over third-party packages
- Max 80 characters per line
- Guard clause pattern (early return, avoid deep nesting)
- snake_case for functions/variables, UPPER_CASE for constants
- One function = one responsibility
- Import order: stdlib, third-party, local (blank line between groups)
- Use async/await for all database and HTTP operations
- Pydantic schemas for all request/response validation
- Alembic for all database schema changes — never modify tables directly

## JavaScript Rules (Frontend — React/Vite)

- Prefer const over let, never use var
- Use async/await over callbacks and .then()
- ESLint config must be present
- Max 80 characters per line
- Destructure imports when possible
- Use Zustand for state management — no prop drilling for global state
- Components in `src/components/`, pages in `src/pages/`
- API calls centralized in `src/api/` modules

## Hermes Agent Rules

- Never edit official packages (`@ai-sdk/*`, `node_modules`, `vendor/`, etc.) — breaks upstream trust.
- Do not pollute `/tmp`. Place all scratch files, test artifacts, and temporary scripts inside the current workdir (e.g. `tests/`, `.scratch/`).
- Use `uv` for Python dependency management and script execution.

## User Preferences

### Language Rules (MANDATORY)

- **Code and documentation: ALWAYS English.** Every file, skill, config, comment, variable name, function name, doc, README — English only. No exceptions.
- **Communication with user: ALWAYS Indonesian.** All conversation, explanations, questions, and responses in Bahasa Indonesia.
- **This rule has been stated hundreds of times. Do not forget. Do not violate.**

## Context

- Languages: Python (backend), JavaScript (frontend)
- Stack: FastAPI + SQLAlchemy (async), React 19 + Vite 8 + Zustand 5
- Project: 9router-fastapi
- Generated: 2026-06-26
