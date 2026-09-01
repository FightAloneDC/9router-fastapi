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
| After proxied chat, `observe_complete` adds this chat to a floor (`quota_cache` / `farmQuota*` / one GET) | `observe_complete` |
| Credits stay **full float** in Python / cache / JSON | `QuotaItem` is `float`; never `int()` / `round()` |
| Tracker UI may show 2 decimal places | `formatQuotaNum` `toFixed(2)` — display only |
| Farm trial vs job-token clocks | quota design §7 |
| Background job-token refresh gated on `expiresAt` | `job_token_needs_refresh` (1h buffer) |
| Tracker list tick does not live-poll Qoder | `USES_UPSTREAM = True`; cache + `/usage` |

Cap `RATE_LIMITS["trial"]["credits"]` = 300 stays an integer
table value. Live **used** is the float.

## Open

### 1. ~~Background refresh ignores job-token TTL~~ — solved

**Fixed 2026-09-01.** `refresh_all_qoder_connections` still runs
every 5 min, but POSTs `jobToken/refresh` only when `expiresAt`
is within `QODER_JOB_TOKEN_REFRESH_BUFFER_S` (1h) or missing
(legacy blob — one refresh writes expiry). Same idea as grok-cli
near-expiry, with a longer buffer because job tokens last ~24 h.
On-demand `try_refresh_connection` on 401/403 is unchanged.

### 2. ~~Quota Tracker still live-polls Qoder~~ — solved

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

### 4. ~~Docs disagree with code~~ — solved

**Fixed 2026-09-02.** Quota design header is **approved**.
§2 list path, full-float credits, and `observe_complete` floor
increment match `quota.py` / `FLOW.md`. Optional item 5 is
not part of that design lock.

### 5. Optional: GET usage after a real job-token refresh

Not built. After a **successful** `jobToken/refresh` (near
`expiresAt`, ~once per day per account), also GET
`quota/usage` with the new Bearer and write `quota_cache`
(`max` with local credits, full float). That is the vendor
source of truth for chats that never hit 9router.

Do **not** GET usage when the refresh cycle skips a still-fresh
token. Tracker ticks already do not poll.

Already exists, not this item: operator card refresh is
`GET /usage/{id}?force=true`. In-use connections may also
re-poll on `/usage` after 15 min. Those are the current
manual / cache paths — they are not the piggyback.

### 6. ~~Import with credits already used~~ — solved

**Fixed 2026-09-02.** `observe_complete` no longer sets
`used = sum(9router credits)`.

1. Cache exists: `cache.used + this chat` (full float).
2. Cache empty + blob `farmQuota*`: farm used + this chat.
3. Cache empty, no farm: **one** GET `quota/usage`, then
   `max(API, local)`. GET failure does not seed a local-only
   bar. Later chats hit (1) and do not GET again.

Do not GET usage on every chat. Item 5 stays optional for
accounts that never chat through 9router and never open the
tracker.

## Suggested order

1. ~~Gate job-token background refresh on `expiresAt`.~~ done.
2. ~~Stop list `GET /quota` from calling Qoder `fetch()`.~~ done.
3. ~~Item 6: `observe_complete` increment + farm floor + one
   GET on first chat if no cache/farm.~~ done.
4. Optional item 5: GET `quota/usage` after a real near-expiry
   `jobToken/refresh` (not `force=true`; that already exists).
5. ~~Align quota design header status if still marked draft.~~
   done.

## Out of scope until asked

- COSY signing, WAF encode, device OAuth, catalog ids
- Other providers’ quota handlers
- Fake UI / hiding the 60 s countdown
