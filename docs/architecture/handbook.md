# 9Router project handbook

Living project detail for humans and agents. Behavioral rules stay in
[`AGENTS.md`](../../AGENTS.md). Ops runbooks:
[development](../operations/development.md),
[production](../operations/production.md).

Self-hosted OpenRouter alternative. Clients send OpenAI-compatible
requests → 9Router resolves a model alias to an upstream provider →
forwards the request → returns the response. Supports 90+ AI
providers with OAuth, API key, free tier, and web cookie auth.

**Faithful port from Next.js (`_reference/`).** When fixing bugs or
adding features, read the original source first and replicate
behavior unless explicitly asked to redesign.

## Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) + Alembic |
| Frontend | React 19 + Vite 8 + Tailwind CSS v4 + Zustand 5 + React Router v7 |
| Database | PostgreSQL 16 |
| Auth | JWT (python-jose HS256, 24h) + bcrypt; password-only login |
| HTTP | httpx (backend→upstream), axios (frontend→backend) |

## Quick start

See [Development ops](../operations/development.md) and
[Production ops](../operations/production.md).

```bash
# Dev (host): UI :5173, API :9000
# Prod: ./scripts/release-prod.sh && docker compose -f docker-compose.prod.yml up --build -d
# App: http://localhost:8013
```

## Layout

```
backend/app/
├── main.py              # FastAPI app factory, lifespan, CORS
├── config.py            # pydantic-settings
├── database.py          # AsyncSession, get_db()
├── models/              # SQLAlchemy models
├── schemas/             # Pydantic schemas
├── routers/
│   ├── auth.py
│   ├── providers/       # connections, models, nodes, catalog, …
│   ├── v1_proxy/        # chat, messages, responses, embeddings, …
│   ├── oauth.py
│   └── …                # combos, usage, quota, mitm, …
├── services/
│   ├── proxy.py         # Model→provider resolution
│   ├── catalog.py
│   ├── token_refresh.py
│   └── …
└── providers/           # PS modules (one folder per provider)

frontend/src/
├── App.jsx
├── api/
├── pages/               # ProvidersPage, ProviderDetailPage, …
├── stores/              # authStore, catalogStore, …
└── components/
```

## Critical patterns

### Catalog and quota live in tables

The connection JSON `data` blob is **not** the catalog.

| Concern | Table |
|---------|--------|
| Model list (fetch / enable / clear) | `provider_models` |
| Quota tracker snapshot | `quota_cache` |
| Chat usage counts | `usage_history` |
| Account row (key, proxy, health) | `provider_connections` + `data` **secrets/health only** |

Set `MODEL_CATALOG_TABLE = True` on the provider config. Fetch/clear
must write `provider_models`, never `data.models`.

Which providers are already on the table is recorded in
[catalog slice notes](2026-08-15-openrouter-catalog-slice.md) (update
that doc when migrating another provider). Do not add new blob
catalogs.

Do not add credential columns to `provider_connections`. Keys stay in
`data` until a dedicated secrets table exists.

### PS architecture

All provider-specific logic lives in
`backend/app/providers/<provider>/`. Frontend gets metadata from
`/providers/catalog` via `catalogStore` — no hardcoded provider lists.

### Alias system

Model strings use short aliases: `"an/claude-sonnet-4"` → alias `an`
→ provider `anthropic`. Backend: `services/proxy.py` → `ALIAS_TO_ID`.
Frontend: derived from catalog.

### Provider categories

| Category | Auth | Examples |
|----------|------|----------|
| Free | None | kiro, qwen, opencode |
| Free Tier | Free API key | openrouter, nvidia, gemini |
| OAuth | OAuth flow | claude, codex, github, cursor, qoder |
| API Key | User's API key | openai, anthropic, deepseek, groq, … |
| Web Cookie | Browser cookie | grok-web, perplexity-web |
| Custom | Custom endpoint | OpenAI/Anthropic-compatible nodes |

### Other

- Sensitive fields (`apiKey`, `accessToken`, `refreshToken`,
  `idToken`) are stripped from `/providers/client` responses.
- Deleting a provider node cascades to connections that reference it.
- OAuth tokens: background refresh via `token_refresh.py`. Qoder:
  on-demand (401/403) + background (~5 min).

## Key files

### Backend

1. `backend/app/main.py`
2. `backend/app/routers/providers/connections.py`
3. `backend/app/services/proxy.py`
4. `backend/app/routers/v1_proxy/`
5. `backend/app/routers/providers/models.py`
6. `backend/app/routers/providers/nodes.py`
7. `backend/app/routers/providers/catalog.py`
8. `backend/app/models/provider.py`
9. `backend/app/schemas/provider.py`
10. `backend/app/services/catalog.py`
11. `backend/app/services/oauth.py`
12. `backend/app/services/token_refresh.py`

### Frontend

1. `frontend/src/App.jsx`
2. `frontend/src/api/providers.js`
3. `frontend/src/stores/catalogStore.js`
4. `frontend/src/pages/ProvidersPage.jsx`
5. `frontend/src/pages/ProviderDetailPage.jsx`
6. `frontend/src/components/OAuthModal.jsx`
7. `frontend/src/stores/authStore.js`

### Provider module

1. `config.py` — Config + Metadata
2. `handler.py` — Request building, validation
3. `constants.py` / `auth.py` / `models.py` / `oauth.py` as needed
4. `FLOW.md` — This provider only (from its code)
5. `backend/app/providers/base.py` — Base classes

### Reference (Next.js)

- `_reference/providers.js`
- `_reference/components/`, `_reference/lib/`, `_reference/store/`,
  `_reference/shared/`

## Debugging workflows

### Provider connection not showing in UI

1. Backend logs / `GET /providers/client`
2. Check snake_case vs camelCase
3. `ProvidersPage` uses `catalogStore` (must be loaded)

### Test connection fails

1. `POST /providers/{id}/test`
2. Console log viewer (`WS /console/ws`)
3. Handler `validationType` and upstream reachability

### Fetch models not working

1. `GET /providers/{conn_id}/models`
2. Handler `fetch_models()` and auth header style
3. Node-based vs built-in provider

### OAuth stuck / Qoder token expired

See provider `FLOW.md` and `token_refresh.py`. Qoder refresh token
is short-lived (~48h); re-import PAT if refresh expired.

## Common commands

```bash
docker compose -f docker-compose.dev.yml up --build
docker compose -f docker-compose.dev.yml exec backend \
  uv run alembic upgrade head

TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')

curl http://localhost:9000/providers/catalog \
  -H "Authorization: Bearer $TOKEN"

cd backend && .venv/bin/pytest tests/ -v
# or: uv run pytest tests/ -v
```

## Related

- [Architecture overview](overview.md)
- [Catalog table slice](2026-08-15-openrouter-catalog-slice.md)
- [Docs index](../README.md)
