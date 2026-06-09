# 9Router FastAPI — Project Study

Tanggal: 2026-06-06
Status: Brainstorming phase 1 (context exploration)

---

## 1. Ringkasan Proyek

9Router adalah self-hosted OpenRouter alternative. Klien mengirim request
OpenAI-compatible → 9Router me-resolve model alias ke upstream provider →
meneruskan request → mengembalikan response. Mendukung 50+ AI provider
(OpenAI, Anthropic, Google, DeepSeek, Groq, dll) dengan berbagai auth:
OAuth, API key, free tier, dan web cookie.

Proyek ini adalah **port dari Next.js** (referensi di `_reference/`).
Prinsip: perilaku harus sesuai original, tidak improvisasi kecuali diminta.

---

## 2. Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | React 19 + Vite 8 + Tailwind CSS v4 + Zustand 5 + React Router v7 |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose HS256, 24h expiry) + bcrypt, password-only login |
| HTTP | httpx (backend→upstream), axios (frontend→backend) |
| Build | uv (backend), npm (frontend), Docker Compose |

---

## 3. Arsitektur

### 3.1 Backend (`backend/app/`)

```
main.py              — App factory, lifespan, CORS, 18 routers
config.py            — pydantic-settings (.env)
database.py          — AsyncSession factory, get_db()
models/              — SQLAlchemy ORM (provider, user, api_key, combo, usage, settings, chat, mitm, cli_tool, proxy_pool)
schemas/             — Pydantic request/response validation
routers/
  auth.py            — /auth/* (login, status, me, register)
  api_keys.py        — /api-keys CRUD
  chat.py            — /chat/conversations, /chat/messages
  cli_tools.py       — /cli-tools CRUD
  combos.py          — /combos CRUD
  console.py         — /console/ws (WebSocket log stream)
  media_providers.py — /media-providers/{kind}
  mitm.py            — /mitm/* proxy management
  models.py          — /models/alias, /models/custom, /models/disabled
  oauth.py           — OAuth flows (PKCE, device code, dll)
  proxy_pools.py     — /proxy-pools CRUD
  providers/         — ★ MODULAR: connections, models, nodes, testing, validation, constants
  quota.py           — Quota tracking
  settings.py        — App settings
  usage.py           — Usage stats/logs/charts
  usage_stream.py    — SSE usage stream
  v1_proxy/          — ★ MODULAR sub-package:
    router.py        — Mounts all v1 endpoint routers
    chat.py          — POST /v1/chat/completions (streaming + non-streaming)
    messages.py      — POST /v1/messages (Claude Messages API compatible)
    responses.py     — POST /v1/responses (OpenAI Responses API)
    embeddings.py    — POST /v1/embeddings
    images.py        — POST /v1/images/generations
    audio.py         — POST /v1/audio/speech, /v1/audio/transcriptions, /v1/audio/voices
    search.py        — POST /v1/search
    web.py           — POST /v1/web/fetch
    models.py        — GET /v1/models, /v1/models/{kind}, /v1/models/info
    shared.py        — Shared utilities (ProxyTarget, fallback helpers, Qoder SSE)
services/
  proxy.py           — ★★ Core: model→provider resolution, ALIAS_TO_ID (82 entries), PROVIDER_CONFIGS, round-robin, cooldown
  auth.py            — bcrypt + JWT
  api_key_auth.py    — API key validation dependency
  oauth.py           — OAuth handlers (1819 lines)
  oauth_providers.py — OAuth config per provider (1489 lines)
  token_refresh.py   — Background token refresh loop
  usage_tracking.py  — Request tracking/persistence
  active_requests.py — In-flight request tracking
  message_translator.py  — Claude ↔ OpenAI format translation
  responses_translator.py — Responses API ↔ Chat Completions translation
  tts_adapters.py    — TTS provider adapters (836 lines)
  stt_adapters.py    — STT provider adapters (449 lines)
  voice_fetchers.py  — Voice listing adapters (403 lines)
  image_adapters.py  — Image generation adapters (202 lines)
  search_adapters.py — Web search adapters (468 lines)
providers/           — ★ NEW modular provider system (78 providers)
  __init__.py        — Provider constants (PROVIDER_*)
  provider.py        — Provider class (unified accessor, lazy-load via importlib)
  ARCHITECTURE.md    — Design documentation
  <provider_name>/   — Per-provider sub-package:
    config.py        — ProviderConfig + ProviderMetadata (Pydantic)
    models.py        — fetch_models(), parse_response()
utils/url.py         — URL utilities
```

### 3.2 Frontend (`frontend/src/`)

```
App.jsx              — 19 routes, all dashboard routes wrapped in ProtectedRoute
api/                 — Axios API modules:
  auth.js, chat.js, cliTools.js, client.js (axios instance + interceptors),
  combos.js, console.js, endpoints.js, mitm.js, models.js, oauth.js,
  providerNodes.js, providers.js (40+ methods), proxyPools.js, quota.js,
  settings.js, usage.js
components/
  layouts/           — AuthLayout, DashboardLayout
  modals/            — AddOpenAICompatibleModal, AddAnthropicCompatibleModal
  ui/                — Badge, Button, Card, Input, Loading, Modal, Toggle
  _originals/        — Original Kiro auth modals (reference)
  *.jsx              — ErrorBoundary, Header, OAuthModal, ProviderTopology, dll
constants/
  providers.js       — ★ Provider definitions (FREE, FREE_TIER, OAUTH, APIKEY, WEB_COOKIE), ALIAS_TO_ID, ID_TO_ALIAS, serviceKinds, MEDIA_PROVIDER_KINDS
  navigation.js      — Sidebar nav
  cliTools.js, mitmTools.js, skills.js
pages/
  LoginPage.jsx, DashboardPage.jsx, EndpointPage.jsx
  ProvidersPage.jsx        — Provider list (1050 lines)
  ProviderDetailPage.jsx   — Provider detail (2179 lines — "jantung project")
  ProviderDetailPage-v1.jsx, ProviderDetailPage-v2.jsx — Older versions
  MediaProvidersPage.jsx, MediaProviderDetailPage.jsx
  CombosPage.jsx, ConsoleLogPage.jsx, ChatPage.jsx
  UsagePage.jsx, QuotaTrackerPage.jsx, SettingsPage.jsx
  MitmPage.jsx, CLIToolsPage.jsx, ProxyPoolsPage.jsx, SkillsPage.jsx
  CallbackPage.jsx         — OAuth callback
stores/
  authStore.js       — Zustand auth state
  notificationStore.js
utils/
  clipboard.js, providerModelsFetcher.js
```

### 3.3 Provider Modular System (BARU — commit terakhir)

Commit `8f83f02` ("feat(providers): implement all 78 API key providers") menambahkan:
- `backend/app/providers/` — 78 provider sub-packages, masing-masing punya `config.py` + `models.py`
- `backend/app/providers/provider.py` — Unified `Provider` class dengan lazy-loading via `importlib`
- `backend/app/providers/ARCHITECTURE.md` — Design doc
- `backend/tests/test_provider_models.py` — 192 baris test
- Total: 238 files changed, +7528/-80 lines

Ini adalah **arsitektur baru yang belum terintegrasi** dengan `services/proxy.py` yang lama.
`proxy.py` masih menggunakan `PROVIDER_CONFIGS` dict hardcoded, bukan `Provider` class.

---

## 4. Provider System — Detail Penting

### 4.1 Data Storage = JSON Blob
Semua provider-specific data disimpan di kolom `data` (TEXT/JSON), BUKAN kolom DB terpisah:
```json
{"apiKey": "...", "models": ["gpt-4"], "baseUrl": "https://...", "testStatus": "connected"}
```

### 4.2 Constants Duplication (Backend + Frontend)
Provider config ada di DUA tempat:
- **Backend lama**: `routers/providers/constants.py` (DEFAULTS) + `services/proxy.py` (PROVIDER_CONFIGS, ALIAS_TO_ID)
- **Backend baru**: `providers/<name>/config.py` (per-provider Pydantic config)
- **Frontend**: `constants/providers.js` (ALIAS_TO_ID, ID_TO_ALIAS, provider definitions)

### 4.3 Alias System
Model strings: `"an/claude-sonnet-4"` → alias "an" → provider "anthropic"
- Backend: `services/proxy.py` → `ALIAS_TO_ID` (82 entries)
- Frontend: `constants/providers.js` → `ALIAS_TO_ID`, `ID_TO_ALIAS`

### 4.4 Provider Categories
| Category | Auth | Count |
|----------|------|-------|
| Free | None | 5 (kiro, qwen, gemini-cli, iflow, opencode) |
| Free Tier | Free API key | 7 (openrouter, nvidia, ollama, vertex, gemini, cloudflare-ai, byteplus) |
| OAuth | OAuth flow | 8 (claude, antigravity, codex, github, cursor, kilocode, cline, qoder) |
| API Key | User's API key | ~50 providers |
| Web Cookie | Browser cookie | 2 (grok-web, perplexity-web) |

### 4.5 Provider Node Cascade
Custom compatible nodes (OpenAI/Anthropic) → connections reference them.
Deleting node auto-deletes all connections referencing it.

---

## 5. v1 Proxy — Endpoint Surface

| Endpoint | Format | Status |
|----------|--------|--------|
| POST /v1/chat/completions | OpenAI | ✅ Selesai (streaming + non-streaming) |
| POST /v1/messages | Claude | ✅ Selesai (translator + streaming) |
| POST /v1/responses | Responses API | ✅ Selesai (translator + streaming) |
| POST /v1/embeddings | OpenAI | ✅ Selesai |
| POST /v1/images/generations | OpenAI | ✅ Selesai |
| POST /v1/audio/speech | TTS | ✅ Selesai (edge-tts verified) |
| POST /v1/audio/transcriptions | STT | ✅ Selesai (Groq, Deepgram, AssemblyAI verified) |
| GET /v1/audio/voices | Voices | ✅ Selesai (gemini, deepgram, edge-tts, local-device) |
| POST /v1/search | Search | ✅ Selesai |
| POST /v1/web/fetch | Fetch | ✅ Selesai (jina-reader, tavily, exa, firecrawl) |
| GET /v1/models | Models list | ✅ Selesai (with kind filter) |
| GET /v1/models/{kind} | Kind filter | ✅ Selesai |
| GET /v1/models/info | Model metadata | ✅ Selesai |

---

## 6. Round-Robin & Cooldown System

Implementasi sudah selesai di `services/proxy.py`:
- **Connection-level round-robin**: fill-first, round-robin, random strategies
- **Cooldown system**: error classification, exponential backoff (base=2s, max=5min)
- **Model lock**: per-model cooldown per connection
- **Fallback loop**: retry with `exclude_connection_ids`

---

## 7. Database & Migrations

11 Alembic migrations:
- Initial tables, providers, combos, usage, API keys, proxy pools, MITM, CLI tools, chat, request details, proxy pool FK

---

## 8. Dokumentasi yang Ada

| File | Isi |
|------|-----|
| AGENTS.md | Behavioral guidelines + project overview |
| CLAUDE.md | Similar to AGENTS.md (for Claude Code) |
| LAPORAN_PROGRES_PORTING.md | Laporan progres porting lengkap |
| TODO_NEXT_PHASE.md | Task list (semua centang — 62 tasks done/skipped) |
| docs/porting-status.md | Gap analysis vs original |
| docs/plans/*.md | 15 plan documents (semua implemented) |
| docs/qa/*.md | QA reports |
| docs/audits/*.md | Audit reports |
| docs/archives/*.md | Historical documents |
| docs/reference/combo-system.md | Combo system reference |
| docs/superpowers/plans/*.md | Superpowers plan |

---

## 9. Temuan Penting

### 9.1 Provider Latency Issue
User melaporkan masalah high latency pada provider. Kemungkinan penyebab:
- Proxy chain: klien → 9Router → upstream provider → response
- Setiap request melibatkan DB query (resolve provider, load connection data)
- `services/proxy.py` masih menggunakan dict hardcoded, bukan cached config
- Tidak ada connection pooling untuk upstream httpx clients

### 9.2 Dual Provider Architecture
Ada dua sistem provider yang co-exist:
1. **Lama**: `services/proxy.py` + `routers/providers/constants.py` (hardcoded dicts)
2. **Baru**: `backend/app/providers/` (modular, per-provider packages)

Sistem baru belum terintegrasi dengan proxy routing. `proxy.py` masih
menggunakan `PROVIDER_CONFIGS` dict, bukan `Provider` class.

### 9.3 Frontend Page Size
- `ProviderDetailPage.jsx`: 2179 lines — sangat besar, perlu perhatian
- `ProvidersPage.jsx`: 1050 lines

### 9.4 Reference Code
`_reference/` berisi original Next.js code:
- `providers.js` (52.5KB) — Original provider definitions
- `components/` — Original component implementations
- `lib/`, `shared/`, `store/` — Original utilities

### 9.5 Docker Dev Environment
- Backend: port 9000 (FastAPI + uvicorn + hot reload)
- Frontend: port 5173 (Vite + hot reload)
- DB: PostgreSQL 16 on port 5432
- OAuth local proxy: port 1455

---

## 10. Status Saat Ini

### Selesai
- Core proxy routing (chat, embeddings, TTS, STT, images, search, fetch, messages, responses)
- 78 API key providers (modular architecture)
- Provider CRUD, validation, testing, model fetch
- OAuth flows (18+ providers)
- Round-robin + cooldown + model lock
- Dashboard UI (19 pages)
- Usage tracking, quota, settings, MITM, CLI tools, proxy pools, console

### Potensi Masalah
- Dual provider architecture (lama vs baru) belum diintegrasikan
- Provider latency (user report)
- Paid provider testing deferred (no credentials)
- Some media validators need cleanup

### Tidak Ada Blokade
Semua core functionality sudah jalan. Project dalam state "lanjutkan" —
bukan "mulai dari nol" atau "terblokir".

---

*Catatan: Dokumentasi ini akan diperbarui setelah brainstorming selesai
dan design spec final ditulis.*
