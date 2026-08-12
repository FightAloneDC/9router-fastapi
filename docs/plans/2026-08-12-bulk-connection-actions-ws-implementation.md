# Bulk Connection Actions (Job + WebSocket) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable / Disable / Test / Delete selected connections via a non-blocking bulk job with WebSocket progress on `/providers/:id`.

**Architecture:** `POST .../bulk-jobs` creates an in-memory job and schedules an asyncio worker. Clients subscribe to `WS /providers/bulk-jobs/ws?token=&jobId=` for `started` / `item` / `progress` / `done` / `error`. Frontend toolbar starts jobs and patches rows from `item` events.

**Tech Stack:** FastAPI WebSocket, asyncio, SQLAlchemy async session factory, React, shared WS helper (usageStream pattern).

**Spec:** `docs/plans/2026-08-12-bulk-connection-actions-ws-design.md`

## Global Constraints

- Code/docs English; user chat Indonesian.
- In-memory job store only (v1); document single-process limit.
- Invalid cross-provider ids → HTTP 400.
- Test concurrency capped (e.g. 3); enable/disable/delete sequential.
- Reuse `_test_provider_connection` and `_renumber_provider_priorities`.
- Do not unify bulk-proxy selection in v1.
- Do not auto-push; user tests before push.
- Use `.venv-test` for pytest — never host `backend/.venv`.
- Register new provider module in `providers/__init__.py`.
- Vite already proxies `/api` with `ws: true`.

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/bulk_connection_jobs.py` | Job store, queues, create/get, publish, TTL cleanup |
| `backend/app/routers/providers/bulk_jobs.py` | POST start + WS + worker |
| `backend/tests/test_bulk_connection_jobs.py` | Unit tests for store + validation helpers |
| `frontend/src/api/bulkJobStream.js` | StrictMode-safe WS subscribe by jobId |
| `frontend/src/api/providers.js` | `startBulkConnectionJob` |
| `frontend/src/pages/ProviderDetailPage.jsx` | Toolbar actions + progress strip |

---

### Task 1: In-memory job service

**Files:**
- Create: `backend/app/services/bulk_connection_jobs.py`
- Test: `backend/tests/test_bulk_connection_jobs.py`

**Interfaces:**
- Produces:
  - `BulkAction = Literal["enable","disable","test","delete"]`
  - `create_job(action: str, provider_id: str, ids: list[str]) -> dict`  
    returns `{jobId, action, total, providerId}`
  - `get_job(job_id: str) -> dict | None`
  - `subscribe(job_id: str) -> asyncio.Queue` / `unsubscribe(job_id, queue)`
  - `publish(job_id: str, event: dict) -> None` (fan-out to subscribers + append to job event log for late joiners optional)
  - `mark_done(job_id, summary)` / `mark_error(job_id, message)`
  - `JOB_TTL_SECONDS = 600`

- [ ] **Step 1: Write failing tests**

```python
"""Unit tests for bulk connection job store."""

import asyncio

from app.services.bulk_connection_jobs import (
    create_job,
    get_job,
    publish,
    subscribe,
    unsubscribe,
)


def test_create_job_returns_id_and_total():
    job = create_job("test", "qoder", ["a", "b", "c"])
    assert job["action"] == "test"
    assert job["total"] == 3
    assert job["providerId"] == "qoder"
    assert get_job(job["jobId"]) is not None


def test_publish_reaches_subscriber():
    async def _run():
        job = create_job("enable", "qoder", ["a"])
        q = subscribe(job["jobId"])
        publish(job["jobId"], {"type": "started", "jobId": job["jobId"]})
        ev = await asyncio.wait_for(q.get(), timeout=1)
        unsubscribe(job["jobId"], q)
        assert ev["type"] == "started"

    asyncio.run(_run())
```

- [ ] **Step 2: Run — expect FAIL (import)**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -m pytest \
  tests/test_bulk_connection_jobs.py -q
```

- [ ] **Step 3: Implement `bulk_connection_jobs.py`**

Keep under ~120 lines. Use `uuid.uuid4().hex`, dict `_jobs`, each job has `subscribers: list[Queue]`, `status`, `createdAt`. `publish` `put_nowait` with drop-on-full. Thread/async safety: single event loop assumed.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** (when execution authorized)

```bash
git add backend/app/services/bulk_connection_jobs.py \
  backend/tests/test_bulk_connection_jobs.py
git commit -m "feat(providers): in-memory bulk connection job store"
```

---

### Task 2: POST bulk-jobs + worker + WebSocket

**Files:**
- Create: `backend/app/routers/providers/bulk_jobs.py`
- Modify: `backend/app/routers/providers/__init__.py` (import bulk_jobs)
- Optionally register nothing in `main.py` if routes hang on providers `router`

**Interfaces:**
- Consumes: job service; `_test_provider_connection`; `_renumber_provider_priorities`; `invalidate_connection_cache`; `async_session` / `AsyncSessionLocal` from `app.database`
- Produces:
  - `POST /providers/by-provider/{provider_id}/connections/bulk-jobs` → 202
  - `WS /providers/bulk-jobs/ws`

- [ ] **Step 1: Implement request schema + start endpoint**

```python
class BulkJobCreate(BaseModel):
    action: Literal["enable", "disable", "test", "delete"]
    ids: list[uuid.UUID]
```

Validate ownership:

```python
rows = (await db.execute(
    select(ProviderConnection.id, ProviderConnection.provider)
    .where(ProviderConnection.id.in_(ids))
)).all()
if len(rows) != len(ids):
    raise HTTPException(400, detail="One or more connections not found")
if any(r.provider != provider_id for r in rows):
    raise HTTPException(400, detail="Connection does not belong to provider")
```

Create job, `asyncio.create_task(run_bulk_job(...))`, return 202 JSON.

- [ ] **Step 2: Implement `run_bulk_job`**

Open a **new** DB session per job (do not use request-scoped session after response):

```python
async with async_session() as db:  # from app.database
    ...
    await db.commit()
```

Per action:

- enable/disable: `conn.is_active = ...`; `publish item` with `isActive`; `invalidate_connection_cache`
- test: call `_test_provider_connection`; write `testStatus` / `lastError` / `lastErrorAt` like single test endpoint (clear lastError on success); publish `testStatus`
- delete: `await db.delete(conn)`; after all deletes, `_renumber_provider_priorities`

For test concurrency=3 use `asyncio.Semaphore(3)` + gather chunks, or process with semaphore around each test.

Emit `started`, then per item `item` + `progress`, then `done` with summary `{total, passed, failed}` (passed/failed meaningful for test; for others passed=ok count).

- [ ] **Step 3: WebSocket endpoint**

Mirror `usage_stream.py` auth. Require `jobId` query. If job missing → close 1008. On connect send `started` snapshot if job exists (or last known status). Loop reading from `subscribe` queue until `done`/`error` or disconnect.

- [ ] **Step 4: Import module in `providers/__init__.py`**

```python
from app.routers.providers import bulk_jobs  # noqa: F401
```

- [ ] **Step 5: Smoke / import check**

```bash
cd backend && PYTHONPATH=. ../.venv-test/bin/python -c \
  "from app.routers.providers import bulk_jobs"
```

Manual (optional if backend up): login → POST bulk-jobs with 1 id → connect WS → see events.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/providers/bulk_jobs.py \
  backend/app/routers/providers/__init__.py
git commit -m "feat(providers): bulk-jobs POST and progress WebSocket"
```

---

### Task 3: Frontend `bulkJobStream.js` + API method

**Files:**
- Create: `frontend/src/api/bulkJobStream.js`
- Modify: `frontend/src/api/providers.js`

**Interfaces:**
- Produces:
  - `subscribeBulkJob(token, jobId, onEvent) => unsubscribe`
  - `providersApi.startBulkConnectionJob(providerId, { action, ids })`

- [ ] **Step 1: Implement WS helper**

Pattern from `usageStream.js`, but keyed by `jobId` (Map of sockets or one socket per active job). URL:

`/api/providers/bulk-jobs/ws?token=...&jobId=...`

Reconnect only while unsubscribe not called and job not terminal. Parse JSON `onmessage` → `onEvent(data)`.

- [ ] **Step 2: API method**

```javascript
startBulkConnectionJob: (providerId, data) =>
  client.post(
    `/providers/by-provider/${providerId}/connections/bulk-jobs`,
    data,
  ),
```

Expect 202; axios should not treat 202 as error (default OK).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/bulkJobStream.js frontend/src/api/providers.js
git commit -m "feat(providers): bulk job WS client and start API"
```

---

### Task 4: ProviderDetailPage toolbar + progress

**Files:**
- Modify: `frontend/src/pages/ProviderDetailPage.jsx`

**Interfaces:**
- Consumes: `startBulkConnectionJob`, `subscribeBulkJob`, existing `selectedConnIds`, confirm modal for delete

- [ ] **Step 1: State**

```javascript
const [bulkJob, setBulkJob] = useState(null)
// { jobId, action, total, done, passed, failed, running }
```

- [ ] **Step 2: `startBulkAction(action)`**

- Guard if `bulkJob?.running` or selection empty
- Delete → existing confirm, then start
- POST with `ids: [...selectedConnIds]`
- Subscribe WS with token from `localStorage` / authStore
- On `item`: `setConnections` patch matching id
- On `progress` / `done` / `error`: update `bulkJob`
- On `done`: unsubscribe, `fetchConnections()`, `setSelectedConnIds(new Set())`, clear running

- [ ] **Step 3: Toolbar UI**

When `selectedConnIds.size > 0`, show Enable / Disable / Test / Delete (count in labels). Disable while `bulkJob?.running`. Keep Select All disabled while running.

Progress strip under toolbar when running:

`Testing 12/47 · 10 ok · 2 fail` (action verb from map).

- [ ] **Step 4: Build check**

```bash
docker compose -f docker-compose.dev.yml exec frontend npm run build
# or npm run build in frontend if deps present
```

Manual: select 2+ connections → Test → see progress without page freeze; Enable/Disable; Delete still confirms.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ProviderDetailPage.jsx
git commit -m "feat(providers): bulk enable/disable/test/delete with WS progress"
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| POST bulk-jobs 202 | 2 |
| WS progress events | 2–3 |
| Ownership 400 | 2 |
| enable/disable/test/delete worker | 2 |
| In-memory TTL store | 1 |
| Toolbar 4 actions | 4 |
| Progress strip + live row patch | 4 |
| Clear selection on done | 4 |
| No proxy selection merge | — |

## Consistency notes

- Path prefix: providers router has no `/api` — Vite strips `/api`.
- Single-test lastError clear-on-success behavior must be mirrored in bulk test worker.
- `create_task` must not use closed request `db` session.
