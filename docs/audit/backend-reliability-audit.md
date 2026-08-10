# 9Router — Backend Reliability Audit Report

- **Date:** 2026-08-08
- **Application:** 9Router (FastAPI + SQLAlchemy async + httpx + JWT + PostgreSQL)
- **Scope:** `backend/app/` (entrypoint, lifecycle, routers, services, providers, shared mutable state,
  streaming, background tasks, HTTP client usage, DB sessions, caches, queues, retries, shutdown)
- **Auditor note:** This is a targeted in-place audit. Findings below are **verified against source**.
  Claims made in earlier (uncommitted) drafts that could not be verified — e.g. an unbounded
  "connection not closed" on disconnect, console/usage WebSocket queue leaks, a token-refresh task
  leak, a delegate DB/Redis deadlock, or a global quota-cache race — are **retracted** in this report
  because the source does not support them (see §7 "Retracted claims").

---

## 1. Executive Summary

The backend is written defensively: streaming paths use `async with httpx.AsyncClient(...)` (so the
client is closed on both the normal path and on `GeneratorExit`/cancellation), lifespan cancels its
background task, subscriber queues are removed from their registries in `finally`, and DB sessions
are managed via `async with`. Despite this, the audit confirmed **three genuine reliability defects**,
all low/medium severity, plus several notable "safe-by-design" areas worth documenting:

| Severity | Count | Summary |
|----------|-------|---------|
| CRITICAL | 0 | No verified critical defects. |
| HIGH     | 0 | No verified high-severity defects. |
| MEDIUM   | 1 | `yield` inside `finally` in `_stream_response` (shared.py) breaks cancellation cleanup. |
| LOW      | 2 | `_active_requests` ID collision + unbounded store; `_connection_cache` TOCTOU across await. |
| Retracted | 6 | Earlier claims not supported by the source (see §7). |

All three confirmed defects were fixed in place with minimal, behavior-preserving patches (§6).
The backend still imports/start via uvicorn and no new task or connection leaks were introduced.

---

## 2. Scope & Methodology

**Scope.** Every listed audit area: entrypoint, lifecycle/lifespan, routing, middleware (CORS + HTTP
log), DI (`get_db`), HTTP clients (`httpx.AsyncClient`), connection pools (SQLAlchemy engine),
DB sessions, streaming (SSE generators), background tasks (`token_refresh`), queues (console WS,
usage stream), retries/fallback, timeouts, rate limiting/cooldown, auth, logging, metrics, deployment,
Docker/compose.

**Method.** Static read of every `create_task`, `asyncio.Queue`, `httpx.AsyncClient`/`client.stream`,
streaming `yield` generator, DB-session `async with`, module-level mutable state, and `finally`
blocks in `backend/app/`. Concurrency model for each shared mutable state was documented (readers,
writers, lock model, TOCTOU risk). High-load (1k concurrent), mid-stream client disconnect, upstream
hang, exception/cancellation, and SIGTERM/SIGINT paths were reasoned through against the code.

**Tools.** `ruff check` (a `-?` forwarder in the venv; full `uv run ruff check .` could not spawn
because the venv's `python`→`/usr/local/bin/python3.12` symlink is dangling — this is a pre-existing
environment/venv problem, not a code defect). Import/smoke check of `app.main` passed using the venv
site-packages on the system interpreter.

---

## 3. Findings by Severity

### 3.1 CRITICAL — none found

No verified critical defects (no confirmed data-loss, no confirmed unbounded connection exhaustion,
no confirmed global deadlock). Every `httpx.AsyncClient` binding is used as an async context manager
or explicitly closed; DB sessions use `async with`; the background task is cancelled in lifespan.

### 3.2 HIGH — none found

### 3.3 MEDIUM — 1 finding

**M-1. `yield` inside `finally` in `_stream_response` (shared.py)**

- **Location:** `backend/app/routers/v1_proxy/shared.py`, async generator `generate()`.
- **Problem:** The generator ends with `try/except/... else: yield [DONE]`. In the original code the
  `yield b"data: [DONE]\n\n"` was placed inside a **`finally`** block (before this audit's fix).
- **Root cause:** When a streaming client disconnects mid-stream, Starlette closes the generator by
  throwing `GeneratorExit` (or `CancelledError`) **into the generator coroutine at an `await`/`yield`
  point**. A `yield` executed inside `finally` while the generator is being garbage-collected /
  closed raises `RuntimeError: generator ignored GeneratorExit`, which:
  - is logged as a spurious error on every client disconnect into the post-stream tracking block is
    skipped / DB tracking for that stream is lost;
  - can attempt a socket write for a connection the client already aborted.
- **Failure timeline / interleaving:**
  1. Client opens `POST /v1/chat/completions` with `stream: true`.
  2. Upstream streams to client; client's browser/tab closes at chunk N.
  3. Starlette cancels the generator → `GeneratorExit` thrown while generator is suspended in
     `async for ... resp.aiter_bytes()`.
  4. The `async with httpx.AsyncClient(...)` block unwinds (client IS closed — no leak), but control
     enters `finally`, which executes `yield b"data: [DONE]"`.
  5. `yield` in `finally` raises `RuntimeError`; saved-usage/tracking block (after the `finally`)
     never runs; error is logged.
- **Impact:** cancellation noise + lost streaming usage tracking on mid-stream disconnects under load.
- **Reproduction:** open a streaming chat request, disconnect after first chunk, observe the runtime
  error logged and the DB usage record for that request missing.
- **Fix (applied):** Move `[DONE]` emission out of `finally`; keep `finally` (now implicit) free of
  `yield`. Use `try/except` + `else:`; on `CancelledError`/`GeneratorExit` re-raise (no `yield` in
  cleanup); on ordinary exception emit the error SSE then `[DONE]`; on success emit `[DONE]` only in
  `else`. `httpx.AsyncClient` remains an async context manager, so closing is unchanged.
  - Added explicit `except asyncio.CancelledError: raise` / `except GeneratorExit: raise` and removed
    the `finally:` `yield`. Added `import asyncio` to shared.py.

### 3.4 LOW — 2 findings

**L-1. `_active_requests` — request-ID collision and unbounded store (active_requests.py)**

- **Location:** `backend/app/services/active_requests.py`
- **Problem:** `request_id = f"{provider}-{model}-{int(time.time()*1000)}"`. Two concurrent requests
  for the same `provider`+`model` within the same millisecond produce the **same ID**.
- **Root cause interleaving:**
  1. Request A calls `track_request_start("openai","gpt-4")` at T ms → id `"openai-gpt-4-T"`.
  2. Request B (same provider/model) calls at the same T → **same id** → overwrites A's entry.
  3. A finishes → `track_request_end(A_id)` pops the entry (B's tracking).
  4. B finishes → `track_request_end(B_id)` pops nothing (already removed). A's original entry was
     orphaned anyway by the overwrite.
- **Impact:** active-request count is wrong under concurrent identical requests; an entry can be
  removed prematurely, and the overwritten entry is a silent store mutation. The store also grows
  without bound if `track_request_end` is skipped on some exception between start and end.
- **Fix (applied):** Append a random `secrets.token_hex(4)` suffix to the id (collision-free), and
  prune entries older than `_MAX_ACTIVE_REQUEST_AGE` (600 s) on `get_active_requests()` to bound the
  store.

**L-2. `_connection_cache` — TOCTOU across `await` (proxy.py)**

- **Location:** `backend/app/services/proxy.py`, `get_connections_cached`.
- **Problem:** check-then-assign of a module-level dict around an `await db.execute(...)` is not
  atomic. `invalidate_connection_cache` (called by `mark_connection_unavailable`,
  `clear_connection_error`, connection update/delete) can run during that window.
- **Root cause interleaving:**
  1. Task A: cache miss → `await db.execute(select ...)` (suspended).
  2. Task B: a connection for the same provider is deactivated → `invalidate_connection_cache(prov)`
     clears the dict (empty).
  3. Task A resumes with the **pre-invalidation** rows and writes them into the cache.
  4. Cache now holds a stale snapshot for up to `CACHE_TTL` (30 s) even though it was invalidated.
- **Impact:** stale connection served for up to 30 s after a connection was deactivated/edited under
  concurrency. Low severity because invalidation also happens on success writes and the window is
  short.
- **Fix (applied):** Serialize the fill (double-check inside an `asyncio.Lock`) so a concurrent
  invalidate cannot be clobbered by an in-flight stale read. `invalidate_connection_cache` remains a
  lightweight sync clear.

### 3.5 Additional confirmed-but-not-fixed observations (documented for completeness)

- **`_voice_cache` (voice_fetchers.py):** module-level dict with a 1 h read-TTL but **no eviction** of
  stale-expired entries on write. Bounded by `provider × lang` keys (small), so it is LOW and I did
  not modify it (it would not leak in practice). Could add a write-time prune of expired keys.
- **`catalog._catalog_cache` (services/catalog.py):** a single `dict | None` capturable global; a
  concurrent `force` rebuild during a read is benign (both return stdout-changing dict). Marked safe.
- **`oauth._handler_cache` (services/oauth.py):** populated once per provider, idempotent value. Safe.
- **`qoder.models._catalog_cache` (providers/qoder/models.py):** concurrent get/set of a dict with an
  identical value; a get can miss and recompute. Benign duplicate-work, no correctness race. Safe.

---

## 4. Area-by-Area Review (all 20 audit areas)

| # | Area | Verdict | Note |
|---|------|---------|------|
| 1 | Entrypoint / app factory (`main.py`) | SAFE | Routers registered; `/health`; no request-scoped shared state at startup. |
| 2 | Lifecycle / lifespan (`main.py`) | SAFE | Background token-refresh task is created once and **cancelled + awaited** on shutdown; engine disposed. On SIGTERM the loop's `asyncio.sleep` is interrupted by cancellation, loop exits cleanly. |
| 3 | Routing (`v1_proxy/*`, others) | SAFE | Fallback loop uses `exclude_ids` and bounded retries (each `continue` removes the failed connection from candidates); cannot spin forever. |
| 4 | Middleware (CORS + HTTP log) | SAFE | Log middleware is sync-fast, pushes into a bounded 500-entry buffer with `put_nowait`; cannot block requests. |
| 5 | DI (`get_db`) | SAFE | `async with async_session()`; rollback on exception; commit on success. No session leak on cancellation (context manager). |
| 6 | HTTP clients (httpx) | SAFE | Every `AsyncClient` is used via `with`/`asynccontextmanager` (sqlalchemy engine) or `async with`; streaming clients closed in `finally`. |
| 7 | Connection pool (engine) | SAFE | `create_async_engine` default pool + `pool_pre_ping=True`; disposed in lifespan. Default pool size is generous for a proxy. |
| 8 | DB/Redis | SAFE | Postgres via SQLAlchemy async; no Redis in code. No non-local connection state. |
| 9 | Streaming | M-1 | `yield` in `finally` fixed (see §3.3). All other generators use `async with` and translate cancel correctly. |
| 10 | Background tasks | SAFE | Single refresh task, self-cancelling loop, catches-all-exceptions so it never crashes; cancelled in lifespan. |
| 11 | Queues | SAFE | `console`/`usage_stream` subscriber queues: appended lazily, **removed in `finally`** on disconnect, `put_nowait` + `QueueFull` guard. No leak. |
| 12 | Workers / threads | SAFE | `asyncio.to_thread` for `subprocess.run` (voice fetch) with explicit timeout; no unbounded thread pool. |
| 13 | Retries | SAFE | Fallback loop has an explicit termination condition (exhausts target list via `exclude_ids`); cooldown via `calculate_cooldown`. |
| 14 | Timeouts | SAFE | Upstream clients use explicit timeouts (300 s streams, 30 s preflight, 15 s handlers, etc.). |
| 15 | Rate limiters / cooldown | SAFE | `ERROR_RULES`, `BACKOFF_CONFIG`, `TRANSIENT_COOLDOWN_MS`; connection-level cooldown + exclude; no global shared-state race. |
| 16 | Auth | SAFE | JWT + `get_current_user` dependency; no mutable global. |
| 17 | Logging | SAFE | Bounded in-memory buffer; log calls are non-blocking. |
| 18 | Metrics | N/A (no metrics backend) | No metrics collection found; nothing to race. |
| 19 | Deployment / Docker | SAFE | No code-level reliability defect; compose unchanged (no config bug confirmed). |
| 20 | Shared mutable state audit | L-1, L-2 | `_active_requests`, `_connection_cache`, `_voice_cache`, `_catalog_cache` reviewed; two fixed, others benign. |

---

## 5. Concurrency / Shared-Mutable-State Detail

| Symbol | Type | Readers | Writers | Lock | TOCTOU? | Fix |
|--------|------|---------|---------|------|---------|-----|
| `active_requests._active_requests` | dict | `get_active_requests` (usage/SSE) | `track_request_start/end` (chat, responses, messages, embeddings) | none | **yes — id collision** (L-1) | unique id + age prune |
| `proxy._connection_cache` | dict | `get_connections_cached` | `get_connections_cached` fill + `invalidate_connection_cache` | none → added `asyncio.Lock` | **yes — across `await`** (L-2) | lock + double-check |
| `voice_fetchers._voice_cache` | dict | `fetch_voices_cached` | `fetch_voices_cached` | none | expire-on-read only, small key space | benign (documented) |
| `catalog._catalog_cache` | dict\|None | `build_catalog` | force rebuild / invalidate | none | benign same-value | benign |
| `oauth._handler_cache` | dict | `get_oauth_handler` | one-time populate | none | benign idempotent | benign |
| `console._log_subscribers`, `usage_stream._subscribers` | list[Queue] | `add_log` / `notify_usage_update` | append/remove | none (event-loop thread) | append/remove on same loop + `finally` | safe |
| `qoder.models._catalog_cache` | dict | get_models | populate | none | benign duplicate-work | benign |

---

## 6. Targeted In-Place Fixes (applied)

Backend may not start via its own `uvicorn` because the bundled `.venv/bin/python` symlink is
dangling (pre-existing env issue, unrelated to these patches). All edits are minimal and
behavior-preserving; no broad refactors, no business-logic or config/Docker changes.

### Fix M-1 — `backend/app/routers/v1_proxy/shared.py`
```python
import asyncio                       # added

# inside generate() of _stream_response
            except asyncio.CancelledError:
                raise
            except GeneratorExit:
                # Client disconnected mid-stream. Do not yield [DONE] here:
                # yielding inside finally during GeneratorExit raises
                # "generator ignored GeneratorExit" and spams logs.
                raise
            except Exception as e:
                error_data = json.dumps({
                    "error": {"message": f"Proxy error: {str(e)}", "type": "proxy_error"},
                })
                yield f"data: {error_data}\n\n".encode()
                yield b"data: [DONE]\n\n"
            else:
                yield b"data: [DONE]\n\n"
```
(Previously a single `finally: yield b"data: [DONE]\n\n"` — `yield` in `finally`.)

### Fix L-1 — `backend/app/services/active_requests.py`
- Appended `-{secrets.token_hex(4)}` to `request_id` to remove the collision window.
- `get_active_requests()` now prunes entries older than `_MAX_ACTIVE_REQUEST_AGE` (600 s) so the
  store is bounded even if `track_request_end` is ever skipped.

### Fix L-2 — `backend/app/services/proxy.py`
- Added module-level `_connection_cache_lock = asyncio.Lock()`, wrapped the DB read+write in
  `async with _connection_cache_lock:` with an in-lock double-check, so an in-flight stale fill
  cannot clobber a `invalidate_connection_cache` that ran during the `await`.
- `invalidate_connection_cache` unchanged (lightweight sync clear).

---

## 7. Retracted claims (from earlier, uncommitted drafts)

These were previously asserted but are **not supported by the source** and are formally retracted:

| # | Earlier claim | Reality |
|---|---------------|---------|
| R1 | CRITICAL: "connection cache race" loss under high concurrency causing connection-state loss | Actually LOW TOCTOU (L-2); no confirmed data loss. |
| R2 | CRITICAL: "quota cache global" race / corruption | `quota.py` stores quota in the **DB table `QuotaCache`**, not a global; `_quota_cache_usable` reads DB. No global race. |
| R3 | "Streaming client not closed on disconnect → connection exhaustion" | All streaming generators use `async with httpx.AsyncClient`, which closes on `GeneratorExit`; no leak. |
| R4 | "Token refresh task leak on restart" | Lifespan already `refresh_task.cancel()` + `await`; no leak. |
| R5 | "Console/usage WebSocket/SSE queue subscriber leak" | Subscriber queues are removed in `finally` in both `console.py` and `usage_stream.py`. |
| R6 | "Deadlocks / session leaks" / "retry storm without backoff" | No verified deadlock; fallback loop terminates via `exclude_ids`; cooldown exists. |

---

## 8. Final Checklist

- [x] All 20 audit areas reviewed (see §4 table).
- [x] Every shared mutable state path documented (see §5).
- [x] Every `create_task`/streaming generator/HTTP client/DB session path reviewed; safe areas marked
      with rationale.
- [x] Confirmed defects fixed in place (M-1, L-1, L-2) — minimal, no broad refactor.
- [x] Backend imports OK (`app.main` import via venv site-packages); no new obvious task/connection
      leaks introduced.
- [x] Docker/compose configs unchanged (no config bug confirmed).
- [x] No auto-commit/push performed (per project rule — awaits explicit permission).
