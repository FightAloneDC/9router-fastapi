# Production Single-Service Design

Date: 2026-08-13  
Status: Approved — implementation plan:
`docs/plans/2026-08-13-production-single-service-implementation.md`

## Goal

Run 9Router in production as **one FastAPI process** that serves both the
built UI and the API. No separate frontend/nginx container. PostgreSQL
remains a separate service. Development stays primarily on the host.

This supports daily self-hosting via the outbound proxy feature without
running a Vite or nginx UI service in production.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Runtime topology | FastAPI only for app; Postgres separate |
| Built UI location | `backend/app/static/` (copied by release script) |
| How artifacts reach `main` | Release script: build → copy → commit to `main` |
| Version tags | Manual (not part of the script) |
| Dev workflow | Host backend + Vite; Postgres in Docker; `docker-compose.dev.yml` kept as fallback |
| Serving approach | Pure FastAPI (StaticFiles + SPA fallback + `/api` strip) |
| OpenAPI UI (`/docs`, `/redoc`, `/openapi.json`) | Enabled only when `DEBUG=true` |
| Release script | `scripts/release-prod.sh` |

## Architecture

### Production

```
Browser ──► :9000 FastAPI
              ├── /api/*     → strip /api → existing routers (+ WS)
              ├── /v1/*      → v1_proxy (always on — daily proxy)
              ├── /docs etc. → OpenAPI (only if DEBUG=true)
              ├── /assets/*  → files under app/static/
              └── /*         → SPA index.html
                    │
Postgres ◄──────────┘ (separate container)
```

Compose services: **`db` + `backend` only**.

### Development (primary)

- Postgres: Docker
- Backend: host (`localhost:9000`, reload)
- Frontend: Vite on host (`localhost:5173`, existing `/api` and `/v1` proxy)

### Development (fallback)

- Existing `docker-compose.dev.yml` (db + backend + frontend) remains available.

## Components

### 1. Static UI tree

- Path: `backend/app/static/`
- Contents: Vite production build output (`index.html`, `assets/`, …)
- `frontend/dist/` stays gitignored (local scratch only)
- `backend/app/static/` is tracked in git (committed on release)
- Keep a small placeholder (e.g. `.gitkeep` + short README) so the folder
  exists before the first release

### 2. FastAPI SPA serving (`backend/app/main.py` or small helper module)

When `app/static/index.html` exists:

1. Register existing API routers as today (no path change on routers)
2. Expose them also under `/api` by stripping the `/api` prefix
   (middleware or equivalent mount) so axios `baseURL: '/api'` works,
   including WebSockets (`/api/console/ws`, `/api/usage/ws`, bulk jobs)
3. Mount static files for hashed assets
4. SPA fallback for non-file, non-API paths → `index.html`

Route priority (must not break):

- Existing API routes and `/api/*`
- `/v1/*`
- `/docs`, `/openapi.json`, `/redoc` (only when `DEBUG=true`)
- Static files
- SPA catch-all last

When static is missing: API keeps working; `GET /` returns a clear
message that the UI was not released yet (no blank page).

**Debug docs in production:** set `DEBUG=true` in backend `.env` and
restart. FastAPI then exposes `/docs`, `/redoc`, and `/openapi.json`
for quick anomaly checks. With `DEBUG=false` (typical prod), those
OpenAPI UI paths are disabled (`docs_url=None`, etc.) so casual
browsers do not land on Swagger.

CORS: keep permissive behavior for Vite origin in dev; production is
same-origin on `:9000`.

### 3. Release script

Path: `scripts/release-prod.sh`

Behavior:

1. Build frontend (`npm ci` if needed, then `npm run build`)
2. Build into a temp dir / replace atomically into `backend/app/static/`
   (never leave a half-written static tree on failure)
3. Stage and commit on `main` with a fixed-style message
   (e.g. `chore: refresh production UI static`)
4. **Do not** create git tags
5. **Do not** touch remotes

Abort rules: any build failure → exit non-zero, no commit, previous
static tree left intact if replace is atomic.

### 4. Docker / Compose

- Add `docker-compose.prod.yml`: `db` + `backend` (prod target), no frontend
- `backend/Dockerfile` prod target copies `app/static/` with the app
- `docker-compose.example.yml`: align with prod shape or point readers
  to `docker-compose.prod.yml`
- Frontend nginx prod image is **not** used by prod compose (may leave
  Dockerfile targets in place but unused / documented as deprecated)

### 5. Docs

- Update `AGENTS.md` quick start: prod vs local-dev paths
- Short note in release script header or `docs/` on how to refresh UI
  on `main`

## Request map (production)

| Client path | Server behavior |
|-------------|-----------------|
| `/api/...` | Strip `/api`, hit existing FastAPI routes |
| `/v1/...` | Existing v1 proxy routers (always available) |
| `/docs`, `/openapi.json`, `/redoc` | FastAPI OpenAPI UI — **only if `DEBUG=true`** |
| Existing static asset paths | Files from `app/static/` |
| React Router paths | `index.html` |

## Out of scope

- TLS / external reverse proxy hardening
- CI that auto-tags or publishes remotes
- Embedding Postgres in the app container
- Removing `docker-compose.dev.yml`
- Large frontend URL refactors (keep `/api` + `/v1` as today)

## Success criteria

1. Prod compose brings up only `db` + `backend`; UI loads on `:9000`
2. Login, provider list, and chat playground work from that UI
3. WebSockets used by the UI work via `/api/...`
4. Host-based Vite + backend + Docker Postgres still works
5. Release script: failed build does not commit; success updates
   `backend/app/static/` on `main`

## Verification

- Automated: light tests for `/api` strip; SPA fallback does not capture
  `/v1`; `/docs` present iff `DEBUG=true`
- Manual smoke: criteria 1–4 above after first release build; flip
  `DEBUG` and confirm `/docs` appears/disappears
