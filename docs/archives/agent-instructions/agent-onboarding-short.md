# 9Router FastAPI — Agent Onboarding
# Berikan prompt ini ke agen CLI di awal sesi baru.
# Prompt: "Baca ~/dev/9router-fastapi/hermes-agent-onboarding.md dulu untuk memahami proyek."

Anda sedang mempelajari proyek **9Router** di `~/dev/9router-fastapi/`.

## TL;DR
9Router = proxy AI model router. Client kirim request → 9Router resolve model ke provider upstream → forward response. Mirip OpenRouter tapi self-hosted.

## Stack
- Backend: Python 3.12 + FastAPI + SQLAlchemy(async) + Alembic → port 9000
- Frontend: React 19 + Vite 8 + Tailwind v4 + Zustand → port 5173
- DB: PostgreSQL 16 (Docker, container: 9router-postgres, user: dev_9route, db: db_9route, port: 5432)
- Auth: JWT HS256 (24h) + bcrypt, password-only login, default "123456"

## Cara Run
```bash
docker compose up -d db
cd backend && uv run alembic upgrade head
docker compose up -d
# → Frontend: http://localhost:5173, Backend: http://localhost:9000/docs
```

## ⚡ Tugas pertama Anda — Baca & Pahami

### WAJIB baca file ini dulu:
1. `backend/app/main.py` — Semua 13 router + lifespan
2. `backend/app/routers/providers/connections.py` — ★ CRUD provider (422 baris, jantung backend)
3. `backend/app/services/proxy.py` — ★★ Core proxy routing (531 baris)
4. `frontend/src/App.jsx` — Routing
5. `frontend/src/pages/ProvidersPage.jsx` — ★ Halaman utama provider (1050 baris)
6. `frontend/src/constants/providers.js` — ★ Semua definisi provider (171 baris)
7. `backend/app/routers/providers/constants.py` — Backend config provider
8. `docs/PROVIDER-FEATURE-MATRIX.md` — ★★ Perbandingan fitur original vs ported
9. `docs/AUDIT-missing-features.md` — ★ Kesenjangan yang diketahui
10. `_reference/providers.js` — Kode Next.js asli (pembanding)

### Struktur Direktori Singkat
```
~/dev/9router-fastapi/
├── docker-compose.yml             # db + backend:9000 + frontend:5173
├── backend/
│   └── app/
│       ├── main.py                # App factory, 13 routers
│       ├── config.py              # pydantic-settings
│       ├── database.py            # AsyncSession
│       ├── models/                # SQLAlchemy models
│       ├── schemas/               # Pydantic schemas
│       ├── routers/               # FastAPI routers
│       │   ├── auth.py            # login, status, me
│       │   ├── providers/         # connections, models, nodes, testing, validation
│       │   ├── v1_proxy.py        # ★ POST /v1/chat/completions (proxy core)
│       │   ├── oauth.py           # OAuth flows
│       │   └── ...                # combos, usage, quota, mitm, cli_tools, dll
│       ├── services/
│       │   ├── proxy.py           # ★★ Model→provider resolution (jantung routing)
│       │   ├── auth.py            # bcrypt + JWT
│       │   ├── oauth.py           # PKCE, OAuth handlers
│       │   └── oauth_providers.py # Config OAuth per provider
│       └── utils/
├── frontend/
│   └── src/
│       ├── App.jsx                # Routes
│       ├── api/providers.js       # 40+ API method
│       ├── constants/providers.js # Semua definisi provider
│       ├── pages/                 # 16 pages
│       └── components/            # UI components + modals
├── _reference/                    # ★ Next.js original (untuk porting reference)
└── docs/                          # Audit docs, QA reports
```

## ★ Pattern KRITIS yang harus diingat:

### 1. Data Provider = JSON Blob
Semua data koneksi provider di kolom `data` (TEXT), BUKAN kolom terpisah:
```json
{
  "apiKey": "sk-...",
  "models": ["gpt-4"],
  "baseUrl": "https://...",
  "testStatus": "connected",
  "lastError": null
  // fields spesifik provider di-merge langsung
}
```
JANGAN tambah kolom baru — masukin ke JSON blob `data`.

### 2. Provider Constants DUPLIKASI di 2 tempat
Backend ✅ Frontend ✅ — HARUS sinkron:
- Backend: `routers/providers/constants.py` (DEFAULTS), `services/proxy.py` (PROVIDER_CONFIGS)
- Frontend: `constants/providers.js`

### 3. Alias System
Model string: `"an/claude-sonnet-4"` (alias "an" → provider "anthropic")
- Backend alias map: `services/proxy.py` → `ALIAS_TO_ID` (82 entry)
- Frontend alias map: `constants/providers.js` → `ALIAS_TO_ID`, `ID_TO_ALIAS`

### 4. Endpoint Kunci untuk Debug
```bash
# Auth
curl -X POST http://localhost:9000/auth/login -H "Content-Type: application/json" -d '{"password":"123456"}'
# → dapat token, simpan sebagai TOKEN

# Provider
curl http://localhost:9000/providers/client -H "Authorization: Bearer $TOKEN"
curl http://localhost:9000/providers -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:9000/providers/{id}/test -H "Authorization: Bearer $TOKEN"
curl http://localhost:9000/providers/{id}/models -H "Authorization: Bearer $TOKEN"

# Proxy (OpenAI-compatible)
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}'
```

### 5. 6 Kategori Provider
| Kategori | Auth | Contoh |
|----------|------|--------|
| Free | No auth | kiro, qwen, opencode |
| Free Tier | API key gratis | openrouter, nvidia, gemini |
| OAuth | OAuth | claude, codex, github, cursor |
| API Key | API key | ~40: openai, anthropic, deepseek, groq |
| Web Cookie | Cookie | grok-web, perplexity-web |
| Custom | Custom endpoint | OpenAI/Anthropic-compatible |

### 6. Optimistic Updates
Toggle aktif/nonaktif update state dulu baru API call. Rollback kalau gagal.

### 7. Auth Flow
- Single password, no username
- Default: "123456"
- Login pertama auto-create admin
- JWT di localStorage key 'token'
- Axios interceptor: attach Bearer, 401→logout

## Dokumen Audit (baca untuk cari masalah)
- `docs/PROVIDER-FEATURE-MATRIX.md` — Fitur per fitur
- `docs/AUDIT-missing-features.md` — Yang hilang
- `docs/AUDIT-PROVIDER-PAGE.md` — Audit provider page

## Langkah Setelah Membaca
1. Identifikasi 3 bug/fitur hilang prioritas tertinggi
2. Untuk setiap bug: trace frontend→API→backend→DB
3. Bandingkan dengan kode di `_reference/` untuk lihat implementasi asli
4. Fix dan verifikasi di browser
