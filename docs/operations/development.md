# Development operations

## Primary workflow (recommended)

1. Keep host Postgres available (`postgres_aidev_db` on `:5432`, or your own).
2. Run backend on the host (`uvicorn` with reload) against `backend/.env`.
3. Run Vite on the host:

```bash
cd frontend && npm run dev
```

- UI: http://localhost:5173 (proxies `/api` and `/v1` to the backend)
- Backend: typically http://localhost:9000

## Compose fallback

```bash
docker compose -f docker-compose.dev.yml up --build
# or the v1 file used historically with host Postgres:
docker compose -f docker-compose-v1.yml up --build
```

## Tests

```bash
cd backend
../.venv-test/bin/pytest tests/ -v
# Prefer project venv; do not rely on Docker-only `.venv`
```

Use `PYTHONPATH` to the worktree/backend path when running from an
isolated checkout.

## Agent / scratch folders

Before creating scratch dirs (`.worktrees/`, `.scratch/`, etc.), add them
to `.gitignore`. Never force-add ignored agent trash into git.
