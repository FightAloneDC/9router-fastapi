# Qoder open problems

Date: 2026-09-01
Status: **open** — inventory, not an implementation plan
Provider: `qoder` (alias `qd`)

Written from live code + operator review the same day.
Do not treat `docs/archives/qoder-docs/` as current policy.

Related:

- Quota bar: `docs/architecture/2026-09-01-qoder-quota-design.md`
- Per-vendor flow: `backend/app/providers/qoder/FLOW.md`
- Token loop: `backend/app/services/token_refresh.py`
- Qoder refresh: `backend/app/providers/qoder/auth.py`

Do **not** change `cosy.py` / device / PAT exchange without
evidence. This list is quota + job-token refresh + tracker
cadence.

## Already fixed (do not reopen)

| Item | Where |
|------|--------|
| Chat SSE `usage.credits` exists and is stored on `usage_history.tokens` | `quota.py` `credits_from_tokens` |
| After proxied chat, local credit sum updates `quota_cache` | `observe_complete` |
| Credits stay **full float** in Python / cache / JSON | `QuotaItem` is `float`; never `int()` / `round()` |
| Tracker UI may show 2 decimal places | `formatQuotaNum` `toFixed(2)` — display only |
| Farm trial vs job-token clocks | quota design §7 |
| Background job-token refresh gated on `expiresAt` | `job_token_needs_refresh` (1h buffer) |
| Tracker list tick does not live-poll Qoder | `USES_UPSTREAM = True`; cache + `/usage` |

Cap `RATE_LIMITS["trial"]["credits"]` = 300 stays an integer
table value. Live **used** is the float.

## Open

### 1. Background refresh ignores job-token TTL

**Fixed 2026-09-01.** `refresh_all_qoder_connections` still runs
every 5 min, but POSTs `jobToken/refresh` only when `expiresAt`
is within `QODER_JOB_TOKEN_REFRESH_BUFFER_S` (1h) or missing
(legacy blob — one refresh writes expiry). Same idea as grok-cli
near-expiry, with a longer buffer because job tokens last ~24 h.
On-demand `try_refresh_connection` on 401/403 is unchanged.

### 2. Quota Tracker still live-polls Qoder

**Fixed 2026-09-01.** `USES_UPSTREAM = True`. `GET /quota` serves
`quota_cache`. Live `quota/usage` is `GET /usage/{id}` (15 min
when in use, or `force=true`). Chat `observe_complete` still
writes the cache so the 60 s tick shows new credits without
hitting Qoder.

Idle rows with no `lastUsedAt` stay on cache until a manual
card refresh or a proxied chat.

### 3. Two clocks, two hosts — easy to mix

| Clock | Host | Auth | Meaning |
|-------|------|------|---------|
| Job token `expiresAt` | openapi | Bearer `jt-` | Credential TTL (~24 h) |
| Trial `expiresAt` / `proTrialEndAt` | quota API / farm | same Bearer | Credit window (~14 d) |
| Chat | `api3` COSY | not the quota GET | Usage; SSE `credits` if proxied |

Chat that never hits 9router (`api3` / IDE) does not write
`usage_history`. Local sum then lags the vendor. `fetch()`
`max(API used, local sum)` exists for that. Direct chat is
not a 9router tracker bug; it is a coverage gap.

Do not use blob `expiresAt` as the credit-bar `reset_at`.

### 4. Docs disagree with code

- Quota design §2 still says credits are **not** summed from
  `usage_history`; the same file later describes
  `observe_complete`. The sum **is** live (`c52577b` era).
- Quota design header still says draft; §2 list path is cache.

FLOW.md is closer to code than the quota design intro.

### 5. Optional: live usage GET on near-expiry refresh

Problem 1 is gated. A successful **near-expiry** refresh is a
reasonable place to write `quota_cache` from the live API
(`max` with local credits, full float). Do not GET usage on
skipped (still-fresh) cycles. Tracker ticks no longer poll.

## Suggested order

1. ~~Gate job-token background refresh on `expiresAt`.~~ done.
2. ~~Stop list `GET /quota` from calling Qoder `fetch()`.~~ done.
3. Optional: live usage GET only on that real refresh (or
   manual `GET /usage/{id}?force=true`).
4. Align quota design header status if still marked draft.

## Out of scope until asked

- COSY signing, WAF encode, device OAuth, catalog ids
- Other providers’ quota handlers
- Fake UI / hiding the 60 s countdown
