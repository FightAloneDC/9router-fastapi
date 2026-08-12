# Configuration

## Backend environment

Primary file: `backend/.env` (gitignored). Template: `backend/.env.example`.

Important keys:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://…`) |
| `SECRET_KEY` | JWT signing |
| `DEBUG` | `true` → enable `/docs`, `/redoc`, `/openapi.json` |
| `ADMIN_PASSWORD` | Seed / login password |
| `CORS_ORIGINS` | `*` or comma-separated origins |
| OAuth client IDs/secrets | Per-provider OAuth |

In **production compose**, `DATABASE_URL` is overridden to reach the host
Postgres via `host.docker.internal` (see `docker-compose.prod.yml`).

## Docker compose files

| File | Use |
|------|-----|
| `docker-compose.prod.yml` | Daily prod: backend only, port `8013`, external DB |
| `docker-compose.dev.yml` | Dev fallback (db + backend + frontend) |
| `docker-compose-v1.yml` | Historical/local variant used with host Postgres |
| `docker-compose.example.yml` | Example prod-shaped compose |

Optional `.env.docker` is only required when a compose file starts its own
Postgres service. Current prod compose does **not** need it.

## Frontend build / static UI

- Source: `frontend/`
- Vite build output: `frontend/dist/` (gitignored scratch)
- Production tree: `backend/app/static/` (committed on `main` via release)

Axios uses `baseURL: '/api'`. Vite and FastAPI strip `/api` to backend
routes. OpenAI clients call `/v1/*` directly.

## Proxy usage (connections)

Per-connection `proxyUsage` in the JSON `data` blob:

- Modes: `off` | `selective` | `all`
- Selective flags include test connection, test model, test chat, OAuth refresh
- Pool may define `default_proxy_usage` and mass-apply to connections

See archived design:
`docs/archives/plans-2026/2026-08-12-connection-proxy-usage-design.md`
