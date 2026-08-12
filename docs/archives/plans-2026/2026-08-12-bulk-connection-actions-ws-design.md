# Design: Bulk Connection Actions via Job + WebSocket

**Date:** 2026-08-12  
**Status:** Approved for planning (pending user review of this file)  
**Scope:** `/providers/:id` — Enable / Disable / Test / Delete on selected connections without blocking HTTP

## Problem

Connection multi-select currently only drives **Delete Selected**. Users also need
bulk enable, disable, and test. Running hundreds of sequential HTTP calls from
the browser is slow and brittle; a long-lived blocking request is worse.

## Goals

- Toolbar actions: **Enable**, **Disable**, **Test**, **Delete** on `selectedConnIds`
  (including Select All filtered).
- Start work with a non-blocking HTTP call; stream progress over **WebSocket**.
- Update visible rows live; avoid freezing the UI.

## Non-goals (v1)

- Unifying the separate bulk-proxy selection state (`selectedConnectionIds`).
- Job cancel / pause.
- Persisting jobs across process restart (Redis, etc.).
- Parallel DDoS of upstream on test (keep low concurrency).

## Decision

**Approach #1:** `POST` starts an in-memory job → background worker → progress on
`WS /providers/bulk-jobs/ws?token=&jobId=`.

## API

### Start job

`POST /providers/by-provider/{provider_id}/connections/bulk-jobs`

Body:

```json
{
  "action": "enable" | "disable" | "test" | "delete",
  "ids": ["uuid", "..."]
}
```

Rules:

- `ids` must be non-empty.
- Every id must belong to `provider_id` — otherwise **400**.
- Response **202**:

```json
{ "jobId": "...", "action": "test", "total": 47 }
```

### Worker behavior

- Run as `asyncio` background task after accept.
- **enable / disable:** set `is_active`, invalidate connection cache.
- **test:** reuse `_test_provider_connection`; persist test status / lastError
  the same way as single-row test where practical.
- **delete:** delete connections; renumber priorities for the provider.
- Processing: sequential for enable/disable/delete; **test** may use a small
  fixed concurrency (e.g. 3) — not unbounded.
- Do not block the start request on completion.

### Progress WebSocket

`WS /providers/bulk-jobs/ws?token=...&jobId=...`

- Auth: JWT via `token` query (same pattern as usage WS).
- Subscribe to one `jobId`; reject if missing/invalid token or unknown job.

Events (JSON):

| type | fields |
|------|--------|
| `started` | `jobId`, `action`, `total` |
| `item` | `jobId`, `connectionId`, `ok`, optional `error`, `testStatus`, `isActive` |
| `progress` | `jobId`, `done`, `total`, optional `passed`, `failed` |
| `done` | `jobId`, `summary` |
| `error` | `jobId`, `message` (fatal job failure) |

### Job store (v1)

- In-memory dict in the backend process.
- Remove finished jobs after ~10 minutes TTL.
- Document: multi-worker / multi-replica needs a shared store later.

## UI (`ProviderDetailPage`)

When `selectedConnIds.size > 0`, show action group (wrap on mobile):

| Button | Action |
|--------|--------|
| Enable | `enable` |
| Disable | `disable` |
| Test | `test` |
| Delete | `delete` (keep confirm modal) |

- Labels may include count: `Enable (N)`.
- While a job is active on this page: disable action buttons and Select All.
- Enable / Disable / Test: **no confirm** in v1 (only Delete confirms).

### Progress strip

Below the toolbar while job runs:

- Text e.g. `Testing 12/47 · 10 ok · 2 fail` (wording by action).
- Optional progress bar from `done/total`.
- On `item`: patch matching row in current page state (`is_active`,
  `test_status`, `lastError` as applicable).
- On `done`: short notification; **one** `fetchConnections()`; **clear**
  selection.

### Frontend WS helper

- Small module e.g. `frontend/src/api/bulkJobStream.js` — StrictMode-safe
  subscribe pattern like `usageStream.js` (shared socket per job, deferred close).

## Success criteria

1. Selecting N connections (including filtered select-all) can Enable, Disable,
   Test, or Delete without the browser waiting on one long HTTP call.
2. Progress updates appear over WebSocket before the job finishes.
3. Visible rows reflect item results; final refetch keeps list consistent.
4. Invalid cross-provider ids are rejected with 400 at start.

## Out of scope follow-ups

- Merge Apply Proxy onto the same `selectedConnIds`.
- Job cancel button.
- Shared job store for horizontal scale.
