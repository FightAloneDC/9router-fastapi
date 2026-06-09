# 9Router Project — Agent Onboarding Brief

Anda adalah agen yang bekerja pada **9Router**, sebuah AI model proxy router dengan web dashboard. Ini adalah proxy/gateway yang duduk di antara aplikasi klien AI (Cursor, Claude Code, client OpenAI-compatible manapun) dan 50+ penyedia AI upstream (OpenAI, Anthropic, Google, DeepSeek, Groq, dll). Anda mengelola koneksi provider, route request, handle OAuth, track usage, dan lainnya.

## Misi Anda

Baca dan pahami seluruh codebase sehingga Anda bisa:
- Debug fitur yang rusak dengan menelusuri round-trip frontend→backend→DB
- Implementasi fitur yang hilang (lihat dokumen audit) dengan membandingkan kode Next.js asli di `_reference/`
- Perbaiki bug di manajemen provider, alur OAuth, proxy routing, atau komponen UI
- Jalankan full stack secara lokal via Docker Compose

## Stack

| Layer | Teknologi |
|-------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | React 19 + Vite 8 + Tailwind CSS v4 + Zustand + React Router v7 |
| Database | PostgreSQL 16 (Docker: 9router-postgres @ localhost:5432) |
| Auth | JWT (python-jose HS256, 24h expiry) + bcrypt |
| HTTP Client | httpx (backend→upstream), axios (frontend→backend) |

## Struktur Direktori

```
~/dev/9router-fastapi/
├── docker-compose.yml              # 3 service: db + backend(:9000) + frontend
├── docker-compose.override.yml     # Override untuk dev
│
├── backend/
│   ├── pyproject.toml              # Python 3.12+, hatchling build
│   ├── Dockerfile                  # Multi-stage: dev → prod
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                  # Alembic async config
│   │   └── versions/               # 9 file migrasi
│   └── app/
│       ├── main.py                 # FastAPI app factory, lifespan (token refresh background), CORS, 13 router
│       ├── config.py               # pydantic-settings: DATABASE_URL, SECRET_KEY, ALGORITHM, DEBUG
│       ├── database.py             # AsyncSession factory, get_db() FastAPI dependency
│       ├── models/
│       │   ├── base.py             # DeclarativeBase + metadata
│       │   ├── user.py             # User (id UUID, username, hashed_password, is_active, timestamps)
│       │   ├── provider.py         # ★ ProviderConnection + ProviderNode — data disimpan sbg JSON blob
│       │   ├── api_key.py          # APIKey untuk /v1 proxy auth
│       │   ├── combo.py            # Combo — grup model
│       │   ├── settings.py         # Global settings (single row)
│       │   ├── usage.py            # Usage analytics
│       │   ├── mitm.py             # MITM interceptor logs
│       │   ├── cli_tool.py         # CLI tool configs
│       │   └── proxy_pool.py       # Proxy pool (rotasi IP)
│       ├── schemas/
│       │   └── provider.py         # Pydantic: ConnectionCreate/Update/Out, Node*, Validate*, Test*, Batch*
│       ├── routers/
│       │   ├── auth.py             # /auth/* — login, status, me (password-only, default "123456")
│       │   ├── providers/          # ★ MODULAR: _router + connections.py + models.py + nodes.py + testing.py + validation.py
│       │   ├── v1_proxy.py         # ★ POST /v1/chat/completions — CORE PROXY (streaming + non-streaming)
│       │   ├── oauth.py            # /oauth/* — PKCE, device code, Codex local proxy, Cursor import
│       │   ├── combos.py           # Combo CRUD
│       │   ├── usage.py            # Usage analytics
│       │   ├── quota.py            # Quota tracking
│       │   ├── mitm.py             # MITM logs
│       │   ├── cli_tools.py        # CLI tool configs
│       │   ├── proxy_pools.py      # Proxy pool CRUD
│       │   ├── models.py           # Model aliases, custom models, disabled models, availability
│       │   ├── api_keys.py         # API keys untuk /v1 proxy
│       │   ├── settings.py         # Global settings
│       │   └── console.py          # WebSocket console log viewer
│       ├── services/
│       │   ├── auth.py             # bcrypt hashing, JWT create/decode, user CRUD
│       │   ├── proxy.py            # ★★ Model→provider resolution, upstream URL/header construction (core routing)
│       │   ├── oauth.py            # PKCE utilities, OAuthService, handler classes (Codex, GitHub, Kiro, Cursor)
│       │   ├── oauth_providers.py  # ★ Konfigurasi OAuth per provider (Claude, Codex, Gemini, GitHub, Kiro, dll — 1390 baris)
│       │   ├── api_key_auth.py     # API key validation untuk /v1 proxy
│       │   └── token_refresh.py    # Background task: refresh OAuth tokens periodically
│       └── utils/
│           └── pkce.py             # PKCE verifier/challenge/state generation
│
├── frontend/
│   ├── package.json                # React 19, Vite 8, Tailwind v4, Zustand 5, React Router 7, Lucide, Recharts
│   ├── vite.config.js              # Proxy /api → localhost:9000 + path rewrite
│   ├── Dockerfile
│   └── src/
│       ├── main.jsx                # Entry with BrowserRouter
│       ├── App.jsx                 # Semua routes dengan ProtectedRoute wrapper, 16 page imports
│       ├── index.css               # Tailwind CSS v4 @import "tailwindcss"
│       ├── api/
│       │   ├── client.js           # Axios instance: Bearer interceptor, 401→logout+redirect
│       │   ├── auth.js             # login(password), status(), verify(), register()
│       │   ├── providers.js        # ★ API provider — 40+ method: CRUD, test, validate, models, nodes, settings
│       │   └── ... (combos.js, mitm.js, usage.js, settings.js, proxyPools.js, etc.)
│       ├── stores/
│       │   ├── authStore.js        # Zustand: login, logout, checkAuth, localStorage token persistence
│       │   └── notificationStore.js
│       ├── pages/                  # 16 page components
│       │   ├── LoginPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── ProvidersPage.jsx   # ★ 1050 baris — provider list with categories, search, toggle, test
│       │   ├── ProviderDetailPage.jsx  # ★ 2179 baris — connections, test, proxy pools, models, OAuth
│       │   ├── MediaProvidersPage.jsx
│       │   ├── MediaProviderDetailPage.jsx
│       │   └── ... (UsagePage, QuotaTrackerPage, MitmPage, CLIToolsPage, SettingsPage, dll)
│       ├── components/
│       │   ├── ui/                 # Badge, Button, Card, Input, Loading, Modal, Toggle
│       │   ├── modals/             # AddOpenAICompatibleModal, AddAnthropicCompatibleModal
│       │   ├── layouts/            # AuthLayout (gradient bg), DashboardLayout (sidebar + header)
│       │   └── ... (OAuthModal, KiroAuthModal, CursorAuthModal, GitLabAuthModal, CompatibleModelsSection, ModelAvailabilityBadge, dll)
│       └── constants/
│           └── providers.js        # ★ ~170 baris — SEMUA definisi provider dengan metadata (name, icon, color, alias, authUrl)
│
├── _reference/                     # ★ KODE NEXT.JS ASLI — untuk referensi porting
│   ├── providers.js                # Halaman providers asli (Next.js App Router)
│   ├── components/
│   │   ├── AddApiKeyModal.js       # Modal add API key asli
│   │   ├── ConnectionRow.js        # Row koneksi asli
│   │   ├── ConnectionsCard.js      # Card koneksi asli
│   │   └── provider-page.js        # Halaman detail provider asli
│   ├── lib/
│   │   ├── providerModelsFetcher.js
│   │   └── providerNormalization.js
│   ├── store/
│   │   └── providerStore.js        # Zustand store asli
│   └── app/
│       ├── models-route.js         # Route models asli
│       ├── suggested-models-route.js
│       ├── test-models-route.js
│       └── test-route.js
│
├── docs/                           # Audit docs, feature matrices, QA reports
│   ├── PROVIDER-FEATURE-MATRIX.md  # ★★ "Original vs Ported" — fitur demi fitur
│   ├── AUDIT-missing-features.md   # ★ Kesenjangan yang diketahui
│   ├── AUDIT-PROVIDER-PAGE.md      # Audit halaman provider
│   ├── plan-kilo-provider-integration.md
│   ├── plan-refactor-providers.md
│   ├── providers-analysis.md
│   ├── providers-integration-test-results.md
│   ├── qa-*.md / qa-*.py          # Laporan dan skrip QA
│   └── features/
│       ├── 01-authentication.md    # Spesifikasi auth
│       └── media-providers.md
│
└── scripts/
    └── test_database.py
```

## Cara Menjalankan Aplikasi

```bash
# 1. Start DB (Docker PostgreSQL 16)
docker compose up -d db

# 2. Jalankan migrasi
cd ~/dev/9router-fastapi/backend && uv run alembic upgrade head

# 3. Start semuanya
cd ~/dev/9router-fastapi && docker compose up -d
```

Akses: Frontend http://localhost:5173, Backend http://localhost:9000, Docs http://localhost:9000/docs

## Arsitektur Core: Cara Proxy Routing Bekerja

Ini adalah **jantung** 9Router — bagaimana request dari client diteruskan ke provider upstream:

```
Client → POST /v1/chat/completions { model: "an/claude-sonnet-4", stream: true }
           ↓
        1. validate_api_key() — cek API key di header Authorization
           ↓
        2. resolve_model_to_targets(db, model, stream)
           ├─ Jika model mengandung "/": parse "provider/model"
           │    • Resolve alias (e.g., "an" → "anthropic", "ds" → "deepseek")
           │    • Cari ProviderConnection aktif dengan provider==resolvedId
           │    • Bangun URL + headers dari config
           ├─ Jika tanpa "/": scan semua ProviderConnection aktif
           │    • Cek apakah model ada di data.models array
           │    • Fallback: koneksi aktif pertama
           └─ Jika combo: resolve setiap model dalam combo
           ↓
        3. _build_upstream_url(provider, base_url, stream, data)
           ├─ "openai" → {base}/chat/completions
           ├─ "anthropic" → {base}/messages
           ├─ "gemini" → {base}/models/{model}:streamGenerateContent?alt=sse
           ├─ "azure" → {endpoint}/openai/deployments/{deployment}/chat/completions?api-version=...
           └─ "cloudflare-ai" → /client/v4/accounts/{accountId}/ai/v1/chat/completions
           ↓
        4. _build_headers(provider, api_key, stream, data)
           ├─ OpenAI-compatible: Authorization: Bearer {key}
           ├─ Anthropic: x-api-key: {key} + anthropic-version: 2023-06-01
           ├─ Google: x-goog-api-key: {key}
           └─ Azure: api-key: {key}
           ↓
        5. Forward request ke upstream, stream response balik (SSE)
```

**File kunci untuk proxy routing:**
- `backend/app/services/proxy.py` — Semua logika routing (531 baris)
- `backend/app/routers/v1_proxy.py` — Endpoint proxy (270 baris)

## Pattern Penyimpanan Data Provider

★ **KRITIS**: Semua data koneksi provider disimpan sebagai JSON blob di kolom `data` (TEXT), BUKAN kolom terpisah:

```python
# ProviderConnection.data — bentuk JSON blob:
{
  "apiKey": "sk-...",                    # SENSITIVE — distrip di /providers/client
  "models": ["gpt-4", "gpt-3.5-turbo"],  # Daftar model yang disimpan
  "roundRobin": false,                    # Round-robin routing
  "baseUrl": "https://api.openai.com/v1", # Base URL kustom
  "displayName": "My OpenAI",             # Nama tampilan
  "globalPriority": 5,                    # Prioritas global
  "defaultModel": "gpt-4",               # Model default
  "testStatus": "connected",              # Status test terakhir
  "lastError": "...",                     # Error terakhir
  "lastErrorAt": "2026-01-01T00:00:00+00:00",
  "connectionProxyEnabled": false,        # Proxy per-koneksi
  "connectionProxyUrl": null,
  "connectionNoProxy": null,
  # ← Fields spesifik provider di-merge langsung ke sini:
  "azureEndpoint": "...",
  "deployment": "...",
  "accountId": "...",
  "prefix": "...",
  "nodeName": "...",
  "apiType": "chat",
}
```

**Helper penting:**
- `_connection_to_out()` di `helpers.py` — extract field dari JSON blob ke schema output
- `_SANITIZE_KEYS` di `constants.py` — field yang dihapus untuk endpoint client
- `_DATA_INTERNAL_KEYS` — field yang BUKAN provider-specific config

## 6 Kategori Provider

| Kategori | Tipe Auth | Contoh |
|----------|-----------|--------|
| **Free** (FREE_PROVIDERS) | No auth / auto | kiro, qwen, gemini-cli, iflow, opencode |
| **Free Tier** (FREE_TIER_PROVIDERS) | API key (gratis) | openrouter, nvidia, ollama, vertex, gemini, cloudflare-ai, byteplus |
| **OAuth** (OAUTH_PROVIDERS) | OAuth flow | claude, antigravity, codex, github, cursor, kilocode, cline |
| **API Key** (APIKEY_PROVIDERS) | API key | ~40 providers: openai, anthropic, deepseek, groq, mistral, together, fireworks, dll |
| **Web Cookie** (WEB_COOKIE_PROVIDERS) | Browser cookie | grok-web, perplexity-web |
| **Custom** (Compatible) | Custom endpoint | OpenAI-compatible, Anthropic-compatible, Custom-embedding |

## Daftar Endpoint API Lengkap

### Auth
- `GET  /auth/status` — Cek status auth (requireLogin, hasPassword)
- `POST /auth/login` — Login dengan password → JWT
- `POST /auth/register` — Register user baru
- `GET  /auth/me` — Info user saat ini (perlu auth)

### Providers (connections)
- `GET    /providers` — Semua koneksi (dengan data sensitif)
- `GET    /providers/client` — Untuk dashboard UI (tanpa data sensitif)
- `POST   /providers` — Buat koneksi baru (auto-validate)
- `GET    /providers/{conn_id}` — Detail satu koneksi
- `PATCH  /providers/{conn_id}` — Update koneksi
- `DELETE /providers/{conn_id}` — Hapus koneksi
- `POST   /providers/{conn_id}/test` — Test koneksi
- `GET    /providers/{conn_id}/models` — Fetch models dari provider API
- `DELETE /providers/{conn_id}/models` — Clear models
- `POST   /providers/validate` — Validasi kredensial
- `POST   /providers/test-batch` — Batch test
- `GET    /providers/suggested-models?url=&type=` — Suggested models

### Provider Nodes (custom endpoints)
- `GET    /provider-nodes` — Semua node
- `POST   /provider-nodes` — Buat node
- `PUT    /provider-nodes/{node_id}` — Update node
- `DELETE /provider-nodes/{node_id}` — Hapus node (cascade ke connection)
- `POST   /provider-nodes/validate` — Validasi kredensial compatible provider

### Models
- `GET    /models/alias` — Lihat alias model
- `PUT    /models/alias` — Set alias model
- `DELETE /models/alias?alias=` — Hapus alias
- `GET    /models/custom` — Custom models
- `POST   /models/custom` — Tambah custom model
- `DELETE /models/custom` — Hapus custom model
- `GET    /models/disabled?providerAlias=` — Disabled models
- `POST   /models/disabled` — Disable models
- `DELETE /models/disabled` — Enable model(s)
- `GET    /models/availability` — Cek cooldown/availability
- `POST   /models/availability` — Clear cooldown
- `POST   /models/test` — Test model

### OAuth
- `GET /oauth/{provider}/auth` — Mulai OAuth flow
- `GET /oauth/{provider}/callback` — OAuth callback
- `POST /oauth/{provider}/token` — Exchange token
- `POST /oauth/{provider}/refresh` — Refresh token
- `POST /oauth/{provider}/device` — Device code flow
- `POST /oauth/codex/proxy/start` — Start Codex local proxy
- `POST /oauth/cursor/import` — Import token Cursor
- `POST /oauth/kiro/token` — Kiro token exchange

### Proxy (core)
- `POST /v1/chat/completions` — ★ Proxy chat completions (OpenAI-compatible)
- `POST /v1/embeddings` — Proxy embeddings (jika diimplementasikan)
- `GET  /v1/models` — Proxy models listing

### Lainnya
- `GET    /health` — Health check
- `GET    /combos` — Combo CRUD
- `GET/POST/PUT/DELETE /usage` — Usage analytics
- `GET/POST/PUT/DELETE /quota` — Quota tracker
- `GET/DELETE /mitm` — MITM logs
- `GET/POST/PUT/DELETE /cli-tools` — CLI tool configs
- `GET/POST/PUT/DELETE /proxy-pools` — Proxy pool management
- `GET/POST/PUT/DELETE /api-keys` — API keys untuk proxy auth
- `GET/PATCH /settings` — Global settings
- `WS /console/ws` — WebSocket console log streaming

## Patterns & Konvensi Penting

1. **Optimistic UI Updates**: Semua toggle (aktif/nonaktif) update state langsung, rollback kalau gagal. Cari `setConnections(prev => prev.map(c => ...` pattern.

2. **JSON Data Blob**: JANGAN tambah kolom baru ke tabel — semua data spesifik provider masuk ke `data` JSON Text column. Baca dulu `constants.py` untuk `_DATA_INTERNAL_KEYS` dan `_SANITIZE_KEYS`.

3. **Alias System**: Setiap provider punya alias 2-5 karakter. Digunakan di model string: `"an/claude-sonnet-4"` (alias "an" → provider "anthropic"). Mapping ada di:
   - Frontend: `constants/providers.js` → `ALIAS_TO_ID`, `ID_TO_ALIAS`
   - Backend: `services/proxy.py` → `ALIAS_TO_ID` (82 entry)

4. **Konstanta Duplikasi**: Konfigurasi provider (URL, auth header, format) ADA DI DUA TEMPAT:
   - Backend: `constants.py` (PROVIDER_DEFAULTS), `proxy.py` (PROVIDER_CONFIGS), `models.py` (PROVIDER_MODELS_CONFIG)
   - Frontend: `constants/providers.js`
   - **Selalu sinkronkan keduanya** saat menambah/mengubah provider.

5. **Auth Flow**: Single password login (tanpa username). Default password `"123456"`. Login pertama auto-create user 'admin'. JWT disimpan di localStorage key `'token'`.

6. **Frontend Routing**: Semua halaman dashboard dibungkus `<ProtectedRoute>` yang cek `authStore.isAuthenticated`. Redirect ke `/login` jika tidak auth.

7. **Axios Interceptors**: 
   - Request: attach `Authorization: Bearer {token}` dari localStorage
   - Response: 401 → hapus token + redirect ke `/login`

8. **Sensitive Data**: `apiKey`, `accessToken`, `refreshToken`, `idToken` distrip dari response endpoint `/providers/client`.

9. **Provider Node Cascade**: Hapus node → otomatis hapus semua connection yang referensi node itu.

## File yang Harus Dibaca Pertama

### Backend (pahami flow end-to-end)
1. `backend/app/main.py` — App factory, lihat semua 13 router
2. `backend/app/routers/providers/connections.py` — ★ CRUD provider (422 baris, paling kompleks)
3. `backend/app/services/proxy.py` — ★★ Core proxy routing (531 baris)
4. `backend/app/routers/v1_proxy.py` — Proxy endpoint (270 baris)
5. `backend/app/routers/providers/models.py` — Model fetching/clearing (563 baris)
6. `backend/app/routers/providers/nodes.py` — Node CRUD + validation (391 baris)
7. `backend/app/models/provider.py` — Model definitions (ProviderConnection + ProviderNode)
8. `backend/app/schemas/provider.py` — Semua Pydantic schema untuk provider (227 baris)
9. `backend/app/services/oauth.py` — OAuth service (1818 baris)
10. `backend/app/services/oauth_providers.py` — OAuth configs per provider (1390 baris)
11. `backend/app/routers/oauth.py` — OAuth endpoints (791 baris)

### Frontend (pahami UI)
1. `frontend/src/App.jsx` — Routing (70 baris)
2. `frontend/src/api/providers.js` — ★ API call definitions (68 baris, 40+ method)
3. `frontend/src/constants/providers.js` — ★ Semua definisi provider (171 baris)
4. `frontend/src/pages/ProvidersPage.jsx` — ★ Halaman utama provider (1050 baris)
5. `frontend/src/pages/ProviderDetailPage.jsx` — ★ Halaman detail provider (2179 baris)
6. `frontend/src/stores/authStore.js` — Auth state management

### Referensi & Audit
1. `docs/PROVIDER-FEATURE-MATRIX.md` — ★★ Fitur per fitur: original vs ported
2. `docs/AUDIT-missing-features.md` — ★ Kesenjangan yang diketahui
3. `docs/AUDIT-PROVIDER-PAGE.md` — Audit spesifik halaman provider
4. `_reference/providers.js` — Original Next.js providers page
5. `_reference/components/provider-page.js` — Original Next.js provider detail page
6. `_reference/components/AddApiKeyModal.js` — Original add API key modal

## Workflow Debugging yang Sering

### Provider Connection tidak muncul di UI
```
1. Cek docker logs: docker compose logs backend
2. Cek GET /providers/client via curl
3. Bandingkan response field names (snake_case vs camelCase issue?)
4. Cek ProvidersPage.jsx line ~146: setConnections(connRes.data?.connections || connRes.data || [])
5. Cek API client.js: apakah 401 interceptor salah trigger?
```

### Test Connection gagal
```
1. Cek POST /providers/{id}/test response
2. Cek backend logs di console log viewer (WS /console/ws)
3. Cek constants.py: apakah validationType benar?
4. Cek validation.py: apakah endpoint /models bisa diakses dari server?
```

### Fetch Models tidak bekerja
```
1. Cek GET /providers/{conn_id}/models
2. Cek PROVIDER_MODELS_CONFIG di models.py — apakah provider punya entry?
3. Cek auth header construction: Bearer vs x-api-key vs query param
4. Cek apakah node-based (compatible) atau built-in provider
```

### OAuth flow stuck
```
1. Cek redirect URI: harus sesuai dengan yang didaftarkan di provider
2. Cek callback endpoint: apakah menerima code dengan benar?
3. Cek token exchange: apakah client_id/secret valid?
4. Codex: cek local proxy server di port 1455
```

## Langkah Pertama Anda

1. Baca `backend/app/main.py` untuk melihat permukaan API lengkap
2. Baca `backend/app/routers/providers/connections.py` untuk CRUD provider (422 baris)
3. Baca `frontend/src/pages/ProvidersPage.jsx` untuk UI utama
4. Baca `frontend/src/constants/providers.js` untuk definisi provider
5. Bandingkan dengan `_reference/providers.js` untuk melihat apa yang asli
6. Baca `docs/PROVIDER-FEATURE-MATRIX.md` untuk perbandingan fitur lengkap
7. Start Docker + jalankan migrasi untuk instance live
8. Identifikasi 3 bug/fitur hilang prioritas tertinggi dari audit docs
