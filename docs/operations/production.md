# Production operations

## First-time / day-to-day start

```bash
# Ensure host Postgres (postgres_aidev_db) is running on :5432
docker compose -f docker-compose.prod.yml up --build -d
```

- App + UI: http://localhost:8013
- OpenAPI: http://localhost:8013/docs only if `DEBUG=true` in `backend/.env`

Do **not** start a separate frontend container. Do **not** replace the
existing Postgres container unless you intentionally migrate data.

## Refresh UI after frontend changes

Must run on branch `main` with a clean working tree:

```bash
git checkout main
./scripts/release-prod.sh
docker compose -f docker-compose.prod.yml up --build -d
```

The script builds Vite, atomically replaces `backend/app/static/`, and
commits. It does not create tags and does not touch remotes.

## Stop / recreate app only (keep DB)

```bash
docker stop 9router-backend 9router-frontend 2>/dev/null || true
docker rm 9router-backend 9router-frontend 2>/dev/null || true
docker compose -f docker-compose.prod.yml up --build -d
```

Never remove `postgres_aidev_db` as part of a normal app redeploy.

## Logs and health

```bash
docker logs 9router-backend --tail 100
curl -s http://127.0.0.1:8013/health
```

## Migrations

Prod container CMD runs `alembic upgrade head` before uvicorn.
