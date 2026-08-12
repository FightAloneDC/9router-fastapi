# 9Router

Self-hosted OpenAI-compatible AI model proxy. Clients talk to 9Router; it
resolves model aliases to upstream providers (OpenAI, Anthropic, Google,
DeepSeek, Qoder, and many others) and returns the response.

Dashboard UI and API run from **one FastAPI process** in production.

## Quick start (production / daily)

Requires an existing Postgres on the host (this project’s usual setup:
`postgres_aidev_db` on port `5432`).

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

- App + UI: http://localhost:8013
- OpenAPI Swagger: only if `DEBUG=true` in `backend/.env` → `/docs`

Refresh the built UI after frontend changes (on `main`, clean tree):

```bash
./scripts/release-prod.sh
docker compose -f docker-compose.prod.yml up --build -d
```

## Quick start (development)

```bash
# Backend (host) + Vite (host); Postgres already on :5432
cd backend && uv run uvicorn app.main:app --reload --port 9000
cd frontend && npm run dev
```

- UI: http://localhost:5173
- API: http://localhost:9000

Compose fallbacks: `docker-compose.dev.yml`, `docker-compose-v1.yml`.

## Documentation

See **[docs/README.md](docs/README.md)** for architecture, configuration,
operations, and gotchas. Historical plans live in `docs/archives/`.

Agent-oriented project rules: [AGENTS.md](AGENTS.md).

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic |
| Frontend | React 19, Vite, Tailwind, Zustand |
| Database | PostgreSQL |
| Auth | JWT + bcrypt |

## License / status

Personal self-hosted proxy. See repository history for release tags.
