# Architecture

9Router is a self-hosted OpenAI-compatible AI proxy. Clients send requests to
9Router; the server resolves a model alias to an upstream provider connection,
forwards the request, and returns the response.

## Runtime topologies

### Production (daily)

- **One app container:** FastAPI serves API + built UI (`backend/app/static/`)
- **Database:** existing host Postgres (`postgres_aidev_db` on `:5432`) — not
  created by `docker-compose.prod.yml`
- **URL:** `http://localhost:8013` (host `8013` → container `9000`)
- **No frontend/Vite/nginx container**

```
Browser ──► :8013 FastAPI
              ├── /api/*     → strip /api → routers (+ WebSocket)
              ├── /v1/*      → OpenAI-compatible proxy (always on)
              ├── /docs*     → OpenAPI UI only if DEBUG=true
              ├── /assets/*  → Vite assets
              ├── /providers/*.png → static icons
              └── UI routes  → SPA index.html (HTML navigations)
                    │
Host Postgres ◄─────┘  (postgres_aidev_db :5432)
```

### Development

- **Primary:** Postgres on host (or compose DB); backend + Vite on the host
- **Fallback:** `docker-compose.dev.yml` / `docker-compose-v1.yml` with
  backend + frontend containers

## Major modules

| Area | Location | Role |
|------|----------|------|
| App factory | `backend/app/main.py` | Routers, middleware, SPA mount |
| Proxy core | `backend/app/services/proxy.py` | Model → connection resolution |
| Outbound proxy | `backend/app/services/outbound_proxy.py` | Per-connection proxy usage |
| Providers (PS) | `backend/app/providers/<name>/` | Provider-specific logic |
| V1 API | `backend/app/routers/v1_proxy/` | Chat, messages, embeddings, … |
| Catalog | `backend/app/services/catalog.py` | Metadata for frontend |
| UI | `frontend/src/` | React dashboard (built into static) |

## Provider data model

Provider-specific fields live in the connection `data` JSON blob (not new
DB columns): API keys, models, `proxyUsage`, test status, etc.

## Related

- [Configuration](../configuration/environment.md)
- [Production operations](../operations/production.md)
- [Gotchas](../gotchas/spa-routing.md)
