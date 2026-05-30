# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

---

## Language Protocol

**Chat & Communication:** Bahasa Indonesia
**Code, Comments, Docs:** 100% English

All Python code, docstrings, commit messages, technical documentation, and inline comments must be written in English. Only use Indonesian for conversational responses to the user.

---

## Git Protocol (STRICT)

**Never execute `git commit`, `git add`, or `git push` unless explicitly instructed by the user.**

- Completing a task or plan does NOT imply permission to commit
- Always wait for user review first
- Every new task starts with a "No Commit" baseline
- Context resets between sessions — never assume prior commit permission carries over

---


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

# 9Router FastAPI — Project Context

## Required Reading (DO NOT SKIP)

1. **Memory files**: Read `/home/mint/.claude/projects/-home-mint-dev-9router-fastapi/memory/MEMORY.md` for project context
2. **_reference/**: Before fixing bugs or adding features, read original source code in `_reference/` first
3. **AGENTS.md**: Follow all instructions in `AGENTS.md` at project root

## Project Overview

**9Router-fastapi** is a faithful port of 9Router Next.js (by decolua)
- Original: `~/dev/9router/` (Next.js 14)
- GitHub: `https://github.com/decolua/9router`
- Reference source: `_reference/` at project root

**Purpose**: Self-hosted OpenRouter alternative. Clients send OpenAI-compatible requests → 9Router resolves model alias to upstream provider → forwards request → returns response. Supports 50+ AI providers.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | React 19 + Vite 8 + Tailwind CSS v4 + Zustand 5 + React Router v7 |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose HS256, 24h expiry) + bcrypt |
| HTTP | httpx (backend→upstream), axios (frontend→backend) |

## Big Picture Plan (User's Vision)

**9Router + Honcho + Multi-Agent System**
- 9Router = LLM routing & cost optimization
- Honcho = memory infrastructure for stateful agents
- Multi-Agent system = CLI agents with persistent memory
- Goal: "make everything free" — optimize costs, use free tiers

## Progress Status (Updated: 2026-05-30)

### ✅ Completed (Committed)

1. **Chat History Persistence** (`feat(chat): add chat history persistence`)
   - Models: `ChatConversation`, `ChatMessage` (backend/app/models/chat.py)
   - Schemas: `MessageCreate`, `MessageOut`, `ConversationCreate`, etc (backend/app/schemas/chat.py)
   - Router: CRUD endpoints in `backend/app/routers/chat.py`
   - Frontend: `frontend/src/api/chat.js` + rewrite `ChatPage.jsx` with sidebar history
   - Migration: `backend/alembic/versions/0fae43bc2187_add_chat_tables.py`

2. **Model Filtering** (`fix(ui): improve chat model filter and compact quota tracker`)
   - Filter in ChatPage: exclude `embed|rerank|tts|stt|robot|voice|deepgram`
   - Type filter: `llm || chat || combo || !type` (empty type allowed)

3. **QuotaTrackerPage UI** (same commit as above)
   - Compact layout: smaller padding, icons, fonts
   - 2-row QuotaBar (merged label+stats), slim progress bar h-1.5
   - Hover effects, tabular-nums alignment

4. **Provider Architecture Plan** (`docs(providers): add architecture plan and provider helper draft`)
   - PLAN.md in `backend/app/providers/`
   - Provider helper draft: `backend/app/providers/cerebras/config.py`
   - Per-provider folder pattern, DRY principle

5. **Qoder Provider — Full Integration**
   - Backend: `backend/app/services/qoder/` — 7 modules (cosy, encoding, transform, models, constants, api, __init__)
   - OAuth device flow + PAT import (OAuthModal.jsx)
   - Model fetching & caching (resolve_qoder_models)
   - Chat completion (streaming + non-streaming) with WAF-bypass body encoding + COSY signing (RSA-1024 + AES-128-CBC + MD5)
   - SSE response parsing (new `{"headers":{...},"body":"..."}` envelope format)
   - Model test endpoint (`/models/test`) — Qoder-specific request building + SSE parsing
   - Proxy routing: `_build_upstream_url`, `_build_headers`, `build_qoder_request` in proxy.py
   - Frontend: `constants/providers.js` (alias: qd, color: #8B5CF6), `public/providers/qoder.png`
   - Auto-refresh model_config cache on first request if empty

### 🚧 Draft / Not Started

1. **Provider Folder Refactoring** (draft only, do NOT touch without approval)
   - `backend/app/providers/` — only cerebras/config.py exists as draft
   - User wants: 1 provider = 1 folder with Pydantic config
   - DO NOT implement, wait for approval

2. **Honcho Integration** (future, not started)
   - Research folder: `/home/mint/tmp/about-honcho/`
   - No code yet, planning phase only

## Rules & User Preferences

### Coding Style
- **English naming** for variables, functions, classes, default values
- **Do NOT correct logic** — user is confident in their logic
- **DO correct naming** — that's their weakness

### File Safety
- **DO NOT touch files with `-v*` suffix** — backup files, in .gitignore
- **DO NOT touch `backend/app/providers/`** without approval — draft area
- **Always read `_reference/`** before fix/new feature — behavior must match original

### Architecture Rules
- **Provider data = JSON blob** in `data` column, DO NOT add new DB columns
- **Constants must sync** between backend and frontend
- **ProviderDetailPage = heart of project** — all features must be working
- **No half-measures** — verify in running app, not just in code

## Key Files

### Backend
- `backend/app/main.py` — FastAPI app, 13 routers
- `backend/app/services/proxy.py` — Core proxy routing (531 lines)
- `backend/app/routers/v1_proxy.py` — Proxy endpoint (270 lines)
- `backend/app/routers/providers/` — Modular: connections, models, nodes, testing, validation
- `backend/app/models/provider.py` — ProviderConnection + ProviderNode
- `backend/app/schemas/provider.py` — Pydantic schemas (227 lines)

### Frontend
- `frontend/src/App.jsx` — Routing (16 pages)
- `frontend/src/pages/ProviderDetailPage.jsx` — Heart of project (2179 lines)
- `frontend/src/pages/ProvidersPage.jsx` — Provider list (1050 lines)
- `frontend/src/constants/providers.js` — Provider definitions (171 lines)
- `frontend/src/stores/authStore.js` — Auth state management

### Reference (Original Next.js)
- `_reference/providers.js` — Original providers page (52KB)
- `_reference/components/` — Original component implementations
- `_reference/lib/`, `_reference/store/`, `_reference/shared/` — Original utilities

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

# View API docs
open http://localhost:9000/docs
```

## Debugging Workflows

### Provider connection not showing in UI
```
1. docker compose -f docker-compose.dev.yml logs backend
2. curl http://localhost:9000/providers/client -H "Authorization: Bearer $TOKEN"
3. Check snake_case vs camelCase field names
4. Check ProvidersPage.jsx: setConnections(connRes.data?.connections || connRes.data || [])
```

### Chat history not saving
```
1. Check migration: docker compose exec backend uv run alembic current
2. Check API: curl http://localhost:9000/chat/conversations -H "Authorization: Bearer $TOKEN"
3. Check browser console for errors
4. Check router prefix: should be /chat not /api/chat (axios baseURL already has /api)
```

### Model filter not working
```
1. Check browser console for filteredModels log
2. Type filter: llm || chat || combo || !type (empty type allowed)
3. Exclude pattern: /embed|rerank|tts|stt|robot|voice|deepgram/i
```
