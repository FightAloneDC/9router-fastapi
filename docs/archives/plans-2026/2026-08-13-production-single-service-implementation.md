# Production Single-Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production runs as one FastAPI process serving the built UI + API (no frontend container); release script refreshes `backend/app/static/` on `main`; OpenAPI UI only when `DEBUG=true`.

**Architecture:** ASGI middleware strips `/api` for same-origin UI calls; Vite build output lives in `backend/app/static/` and is served with SPA fallback; `/v1` stays always-on for proxy clients; `scripts/release-prod.sh` builds UI and commits static assets to `main` (no tags, no remotes).

**Tech Stack:** FastAPI/Starlette, Vite build, Docker Compose, bash release script.

**Spec:** `docs/plans/2026-08-13-production-single-service-design.md`

## Global Constraints

- Code/docs English; user chat Indonesian.
- No separate frontend/nginx service in production compose.
- `/v1` always available (daily OpenAI-compatible proxy).
- OpenAPI UI (`/docs`, `/redoc`, `/openapi.json`) only when `DEBUG=true`.
- Built UI path: `backend/app/static/` (tracked); `frontend/dist/` stays ignored.
- Release script: `scripts/release-prod.sh` — build → atomic copy → commit on `main`; no tags; do not touch remotes.
- Do not delete `docker-compose.dev.yml`.
- Use `../.venv-local/bin/pytest` or project `.venv-test` for tests — never rely on Docker-only `.venv` for host pytest.
- Max 80 characters per Python line where practical.
- Do not auto-commit/tag/touch remotes unless the user explicitly asks during execution (plan commit steps are optional checkpoints).

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/openapi_ui.py` | Docs URL kwargs from `DEBUG` |
| `backend/app/middleware/api_prefix.py` | Strip `/api` for HTTP + WebSocket |
| `backend/app/static_ui.py` | Mount static assets + SPA fallback + missing-UI message |
| `backend/app/main.py` | Wire DEBUG docs, middleware, static UI |
| `backend/app/static/README.md` + `.gitkeep` | Placeholder until first release |
| `backend/tests/test_openapi_ui.py` | DEBUG gating |
| `backend/tests/test_api_prefix.py` | `/api` strip |
| `backend/tests/test_static_ui.py` | SPA + missing index |
| `scripts/release-prod.sh` | Build + atomic copy + commit on `main` |
| `docker-compose.prod.yml` | `db` + `backend` only |
| `docker-compose.example.yml` | Point at / match prod shape |
| `AGENTS.md` | Prod vs local-dev quick start |
| `.gitignore` | Ensure `backend/app/static/` is not ignored |

---

### Task 1: DEBUG-gated OpenAPI UI

**Files:**
- Create: `backend/app/openapi_ui.py`
- Modify: `backend/app/main.py` (`create_app` FastAPI constructor)
- Test: `backend/tests/test_openapi_ui.py`

**Interfaces:**
- Produces: `openapi_ui_kwargs(debug: bool) -> dict[str, str | None]`  
  Keys: `docs_url`, `redoc_url`, `openapi_url`  
  When `debug` is True → `"/docs"`, `"/redoc"`, `"/openapi.json"`  
  When False → all `None`

- [ ] **Step 1: Write failing tests**

```python
"""OpenAPI UI is exposed only when DEBUG is true."""

from app.openapi_ui import openapi_ui_kwargs


def test_openapi_enabled_when_debug():
    kw = openapi_ui_kwargs(True)
    assert kw["docs_url"] == "/docs"
    assert kw["redoc_url"] == "/redoc"
    assert kw["openapi_url"] == "/openapi.json"


def test_openapi_disabled_when_not_debug():
    kw = openapi_ui_kwargs(False)
    assert kw["docs_url"] is None
    assert kw["redoc_url"] is None
    assert kw["openapi_url"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_openapi_ui.py -v`  
(Fallback: `../.venv-test/bin/pytest` if `.venv-local` missing.)  
Expected: FAIL — `ModuleNotFoundError` or import error for `app.openapi_ui`

- [ ] **Step 3: Implement helper + wire `create_app`**

```python
# backend/app/openapi_ui.py
"""OpenAPI / Swagger UI gating for production."""


def openapi_ui_kwargs(debug: bool) -> dict[str, str | None]:
    if debug:
        return {
            "docs_url": "/docs",
            "redoc_url": "/redoc",
            "openapi_url": "/openapi.json",
        }
    return {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
```

In `create_app`, change FastAPI construction to:

```python
from app.openapi_ui import openapi_ui_kwargs

app = FastAPI(
    title="9Router",
    description="AI model proxy router with web dashboard",
    version="0.1.0",
    lifespan=lifespan,
    **openapi_ui_kwargs(settings.DEBUG),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_openapi_ui.py -v`  
Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add backend/app/openapi_ui.py backend/app/main.py \
  backend/tests/test_openapi_ui.py
git commit -m "$(cat <<'EOF'
feat: gate OpenAPI UI behind DEBUG

EOF
)"
```

---

### Task 2: `/api` prefix strip middleware

**Files:**
- Create: `backend/app/middleware/__init__.py` (empty or package docstring)
- Create: `backend/app/middleware/api_prefix.py`
- Test: `backend/tests/test_api_prefix.py`

**Interfaces:**
- Produces: `StripApiPrefixMiddleware` — pure ASGI middleware  
  For `http` and `websocket` scopes: if path is `/api` or starts with `/api/`, rewrite `scope["path"]` to path without the `/api` prefix (`/api` → `/`, `/api/auth/login` → `/auth/login`).  
  Do not rewrite `/v1` or other paths.  
  Do not change `root_path`.

- [ ] **Step 1: Write failing tests**

```python
"""Strip /api prefix for same-origin UI clients."""

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.middleware.api_prefix import StripApiPrefixMiddleware


def _app_with_middleware() -> FastAPI:
    app = FastAPI()
    app.add_middleware(StripApiPrefixMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/auth/status")
    async def auth_status():
        return {"ok": True}

    @app.websocket("/console/ws")
    async def console_ws(ws: WebSocket):
        await ws.accept()
        await ws.send_text("pong")
        await ws.close()

    return app


def test_api_prefix_rewrites_http():
    client = TestClient(_app_with_middleware())
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/status").json() == {"ok": True}


def test_bare_paths_still_work():
    client = TestClient(_app_with_middleware())
    assert client.get("/health").json() == {"status": "ok"}


def test_v1_not_stripped_as_api():
    """Path /v1 must not be treated as /api strip target."""
    app = _app_with_middleware()

    @app.get("/v1/chat/completions")
    async def chat():
        return {"object": "chat"}

    client = TestClient(app)
    assert client.get("/v1/chat/completions").status_code == 200
    # /api/v1/... would strip to /v1/... — UI does not use that;
    # ensure /v1 itself is unchanged when called directly.
    assert client.get("/v1/chat/completions").json()["object"] == "chat"


def test_api_prefix_rewrites_websocket():
    client = TestClient(_app_with_middleware())
    with client.websocket_connect("/api/console/ws") as ws:
        assert ws.receive_text() == "pong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_api_prefix.py -v`  
Expected: FAIL — cannot import `StripApiPrefixMiddleware`

- [ ] **Step 3: Implement middleware**

```python
# backend/app/middleware/api_prefix.py
"""Rewrite /api/* to /* for same-origin dashboard calls."""

from __future__ import annotations

from typing import Callable


class StripApiPrefixMiddleware:
    """ASGI middleware: strip leading /api for HTTP and WebSocket."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path") or ""
            if path == "/api" or path.startswith("/api/"):
                new_path = path[4:] or "/"
                scope = dict(scope)
                scope["path"] = new_path
        await self.app(scope, receive, send)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_api_prefix.py -v`  
Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add backend/app/middleware/ backend/tests/test_api_prefix.py
git commit -m "$(cat <<'EOF'
feat: strip /api prefix for same-origin UI

EOF
)"
```

---

### Task 3: Static UI mount + SPA fallback

**Files:**
- Create: `backend/app/static_ui.py`
- Test: `backend/tests/test_static_ui.py`

**Interfaces:**
- Produces:
  - `STATIC_DIR: Path` — default `Path(__file__).resolve().parent / "static"`
  - `mount_static_ui(app: FastAPI, static_dir: Path | None = None) -> None`  
    - If `static_dir / "index.html"` **missing**: register `GET /` returning JSON  
      `{"detail": "UI not released. Run scripts/release-prod.sh"}` with 503  
      (or 200 with clear message — prefer **503** so monitors notice).  
    - If present:  
      1. If `assets/` exists, `app.mount("/assets", StaticFiles(...), name="ui-assets")`  
      2. Register catch-all `GET /{full_path:path}` **last** that:  
         - serves existing files under `static_dir` via `FileResponse`  
         - otherwise returns `index.html` (SPA)  
      3. Also handle `GET /` → `index.html`  
    - Must not register routes that override `/health` if those were already  
      added — call `mount_static_ui` **after** API routers + `/health` in `main.py`  
      (wiring is Task 4). Tests use a minimal app and call mount last.

- [ ] **Step 1: Write failing tests**

```python
"""Serve built UI from app/static with SPA fallback."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_ui import mount_static_ui


def test_missing_index_returns_clear_error(tmp_path: Path):
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    mount_static_ui(app, tmp_path)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    res = client.get("/")
    assert res.status_code == 503
    assert "release-prod" in res.json()["detail"]


def test_serves_index_and_spa_fallback(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<!doctype html><title>9Router</title>", encoding="utf-8"
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models():
        return {"data": []}

    mount_static_ui(app, tmp_path)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/v1/models").json() == {"data": []}
    assert "9Router" in client.get("/").text
    assert "9Router" in client.get("/providers").text
    assert client.get("/assets/app.js").text == "console.log(1)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_static_ui.py -v`  
Expected: FAIL — cannot import `mount_static_ui`

- [ ] **Step 3: Implement `static_ui.py`**

```python
# backend/app/static_ui.py
"""Serve Vite production build from app/static."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).resolve().parent / "static"
_MISSING_DETAIL = (
    "UI not released. Run scripts/release-prod.sh"
)


def mount_static_ui(
    app: FastAPI,
    static_dir: Path | None = None,
) -> None:
    root = static_dir or STATIC_DIR
    index = root / "index.html"

    if not index.is_file():
        @app.get("/")
        async def ui_missing():
            raise HTTPException(
                status_code=503,
                detail=_MISSING_DETAIL,
            )
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets),
            name="ui-assets",
        )

    @app.get("/")
    async def ui_index():
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Never shadow API-looking paths if they somehow hit here;
        # routers registered earlier win in Starlette routing.
        candidate = root / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)
```

Note: In Starlette/FastAPI, routes registered earlier take precedence over
later path parameters for the same method only when specificity matches —
mounted `/assets` and explicit API routes added **before** `mount_static_ui`
must win. Tests assert `/health` and `/v1/models` still work.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv-local/bin/pytest tests/test_static_ui.py -v`  
Expected: PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add backend/app/static_ui.py backend/tests/test_static_ui.py
git commit -m "$(cat <<'EOF'
feat: serve SPA static UI from app/static

EOF
)"
```

---

### Task 4: Wire into `main.py` + static placeholder + gitignore

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/app/static/.gitkeep`
- Create: `backend/app/static/README.md`
- Modify: `.gitignore` (ensure static is tracked)

**Interfaces:**
- Consumes: `openapi_ui_kwargs`, `StripApiPrefixMiddleware`, `mount_static_ui`
- After all `include_router` + `/health`, call `mount_static_ui(app)`
- Add `StripApiPrefixMiddleware` with other middleware (order: add after CORS is fine; stripping must run before routing — Starlette middleware is outer-first)

- [ ] **Step 1: Add placeholder files**

`backend/app/static/README.md`:

```markdown
# Production UI static files

Populated by `scripts/release-prod.sh` from the Vite build.
Do not edit by hand. `frontend/dist/` remains a local scratch folder.
```

`backend/app/static/.gitkeep` — empty file.

- [ ] **Step 2: Update `.gitignore`**

Keep `frontend/dist/` and root `dist/`. Add an explicit allow so production
static is never accidentally ignored:

```gitignore
# Production UI served by FastAPI (release-prod.sh)
!backend/app/static/
!backend/app/static/**
```

Place near the existing `frontend/dist/` / `dist/` section.

- [ ] **Step 3: Wire `main.py`**

After CORS middleware registration, add:

```python
from app.middleware.api_prefix import StripApiPrefixMiddleware

app.add_middleware(StripApiPrefixMiddleware)
```

(Keep existing request-logging middleware.)

At end of `create_app`, after `/health`, before `return app`:

```python
from app.static_ui import mount_static_ui

mount_static_ui(app)
```

Ensure Task 1 OpenAPI kwargs remain wired.

- [ ] **Step 4: Regression tests**

Run:

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_openapi_ui.py \
  tests/test_api_prefix.py \
  tests/test_static_ui.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add backend/app/main.py backend/app/static/ .gitignore
git commit -m "$(cat <<'EOF'
feat: wire SPA serving and /api strip into app

EOF
)"
```

---

### Task 5: `scripts/release-prod.sh`

**Files:**
- Create: `scripts/release-prod.sh` (executable)

**Interfaces:**
- Behavior (must match spec):
  1. `set -euo pipefail`
  2. Resolve repo root from script location
  3. Require current git branch is `main` (exit 1 with message otherwise)
  4. Require clean working tree before starting (`git status --porcelain` empty),  
     so the only commit is the static refresh
  5. `cd frontend`
  6. If `node_modules` missing → `npm ci`
  7. `npm run build` (writes `frontend/dist`)
  8. Atomic replace:
     - `STATIC=backend/app/static`
     - `TMP=$(mktemp -d)`
     - copy `frontend/dist/.` → `$TMP/`
     - keep `README.md` from old static if present (copy into `$TMP` if not  
       in dist)
     - `rm -rf "$STATIC"` then `mkdir -p` parent and `mv "$TMP" "$STATIC"`  
       OR: rsync into a sibling `static.next` then `mv` swap  
     - On any failure before swap, leave existing `$STATIC` intact
  9. `git add backend/app/static`
  10. If nothing staged / no diff → print "No UI changes" and exit 0
  11. `git commit -m "chore: refresh production UI static"`
  12. Never create tags; never call remote update commands

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Build Vite UI into backend/app/static and commit on main.
# Does not create tags. Does not touch remotes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
STATIC="$ROOT/backend/app/static"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"

if [[ "$BRANCH" != "main" ]]; then
  echo "error: checkout main before release (on $BRANCH)" >&2
  exit 1
fi

if [[ -n "$(git -C "$ROOT" status --porcelain)" ]]; then
  echo "error: working tree not clean" >&2
  exit 1
fi

cd "$FRONTEND"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$FRONTEND/dist/." "$TMP/"
if [[ -f "$STATIC/README.md" && ! -f "$TMP/README.md" ]]; then
  cp "$STATIC/README.md" "$TMP/README.md"
fi

# Atomic swap
NEXT="$ROOT/backend/app/static.next"
rm -rf "$NEXT"
mv "$TMP" "$NEXT"
trap - EXIT
rm -rf "$STATIC"
mv "$NEXT" "$STATIC"

git -C "$ROOT" add backend/app/static
if git -C "$ROOT" diff --cached --quiet; then
  echo "No UI changes"
  exit 0
fi

git -C "$ROOT" commit -m "chore: refresh production UI static"
echo "Committed production UI static on main."
```

Make executable: `chmod +x scripts/release-prod.sh`

- [ ] **Step 2: Dry-run checks (no commit if not on main / dirty)**

From a dirty or non-`main` branch (current `dev` is fine):

```bash
./scripts/release-prod.sh
```

Expected: exits 1 with branch or dirty-tree message (do **not** switch
branches just to force a real commit in this task unless the user asks).

- [ ] **Step 3: Commit the script (only if user asked)**

```bash
git add scripts/release-prod.sh
git commit -m "$(cat <<'EOF'
chore: add release-prod.sh for UI static on main

EOF
)"
```

---

### Task 6: Compose prod + docs

**Files:**
- Create: `docker-compose.prod.yml`
- Modify: `docker-compose.example.yml` (header comment + align to db+backend)
- Modify: `AGENTS.md` (Quick Start section)
- Optionally comment in `frontend/Dockerfile` prod stage: unused by prod compose

**Interfaces:**
- `docker-compose.prod.yml`: services `db` + `backend` only  
  - backend `target: prod`, ports `9000:9000` (+ `1455:1455` if Codex local  
    proxy still needed in prod — keep `1455` for parity with current OAuth)  
  - `env_file`: `./backend/.env` + `.env.docker`  
  - `depends_on` db healthy  
  - `restart: unless-stopped`  
  - No frontend service

- [ ] **Step 1: Write `docker-compose.prod.yml`**

```yaml
# Production — single FastAPI serves API + built UI
# Usage: docker compose -f docker-compose.prod.yml up --build -d
# Refresh UI on main first: ./scripts/release-prod.sh

services:
  db:
    image: postgres:16-alpine
    container_name: 9router-postgres
    restart: unless-stopped
    env_file:
      - .env.docker
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: prod
    container_name: 9router-backend
    restart: unless-stopped
    ports:
      - "9000:9000"
      - "1455:1455"
    env_file:
      - ./backend/.env
      - .env.docker
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 2: Update `docker-compose.example.yml`**

Replace frontend service with a top comment:

```yaml
# Example production-shaped compose (db + backend only).
# Preferred file: docker-compose.prod.yml
# UI is served by FastAPI from backend/app/static (see scripts/release-prod.sh).
```

Remove the `frontend:` service block so the example matches prod.

- [ ] **Step 3: Update `AGENTS.md` Quick Start**

Replace/extend the Quick Start block roughly as:

```markdown
## Quick Start

### Production (daily use)
```bash
# On main, after UI changes:
./scripts/release-prod.sh
docker compose -f docker-compose.prod.yml up --build -d
# App+UI: http://localhost:9000
# Swagger: only if DEBUG=true in backend/.env → /docs
```

### Development (primary — host + DB Docker)
```bash
docker compose -f docker-compose.dev.yml up db -d
# backend on host :9000, Vite on host :5173
```

### Development (fallback — full compose)
```bash
docker compose -f docker-compose.dev.yml up --build
# Frontend: http://localhost:5173
# Backend: http://localhost:9000/docs  (DEBUG)
```
```

Keep existing architecture tables; do not remove PS rules.

- [ ] **Step 4: Note on `frontend/Dockerfile`**

At the top of the `# ── Production ──` nginx stage, add:

```dockerfile
# Deprecated for compose prod: UI is served by FastAPI (app/static).
# Kept for optional standalone nginx experiments only.
```

- [ ] **Step 5: Commit (only if user asked)**

```bash
git add docker-compose.prod.yml docker-compose.example.yml \
  AGENTS.md frontend/Dockerfile
git commit -m "$(cat <<'EOF'
chore: add production compose (single backend + UI)

EOF
)"
```

---

### Task 7: Final verification

**Files:** none new (smoke only)

- [ ] **Step 1: Unit suite for this feature**

```bash
cd backend && ../.venv-local/bin/pytest \
  tests/test_openapi_ui.py \
  tests/test_api_prefix.py \
  tests/test_static_ui.py -v
```

Expected: all PASS

- [ ] **Step 2: Manual checklist (report outcomes, do not claim success early)**

1. With placeholder static (no `index.html`): `GET /` → 503 message  
2. Copy a minimal `index.html` into `backend/app/static/` locally → `GET /` HTML  
3. `DEBUG=false`: `/docs` → 404; `DEBUG=true`: `/docs` → 200  
4. `/api/health` → same as `/health`  
5. `/v1` routes still registered (import/app routes list or hit a known 401/422)  
6. Confirm `docker-compose.prod.yml` has no `frontend` service:  
   `grep -c 'frontend:' docker-compose.prod.yml` → `0`

- [ ] **Step 3: First real `release-prod.sh` on `main`**

Only when the user explicitly wants a production UI commit on `main`:
checkout `main`, ensure clean tree, run `./scripts/release-prod.sh`, then
`docker compose -f docker-compose.prod.yml up --build -d` and smoke login.

Do not touch remotes.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Single FastAPI serves UI+API | 3, 4, 6 |
| No frontend service in prod | 6 |
| Postgres separate | 6 |
| `backend/app/static/` + placeholder | 3, 4 |
| `/api` strip + WS | 2, 4 |
| `/v1` always on | 3 tests + 6 (unchanged routers) |
| OpenAPI only if `DEBUG=true` | 1 |
| `scripts/release-prod.sh` build+commit on main, no tags/remotes | 5 |
| `docker-compose.prod.yml` | 6 |
| Dev host primary + compose.dev fallback | 6 (`AGENTS.md`) |
| Missing static clear error | 3 |
| Automated tests for strip / SPA / docs | 1–3, 7 |

No TBD placeholders. Interface names consistent across tasks
(`openapi_ui_kwargs`, `StripApiPrefixMiddleware`, `mount_static_ui`,
`scripts/release-prod.sh`).
