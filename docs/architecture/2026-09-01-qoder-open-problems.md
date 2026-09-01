# Qoder open problems

Date: 2026-09-01
Status: **closed** (2026-09-02) — inventory complete
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
| Farm trial vs job-token clocks | `bulk.py` + quota design §7 |
| PAT persisted for late re-exchange | blob `personalToken` |
| Background job-token refresh gated on `expiresAt` | `job_token_needs_refresh` (1h buffer) |
| Tracker list tick does not live-poll Qoder | `USES_UPSTREAM = True`; cache + `/usage` |
| GET `quota/usage` after a real job-token refresh | `sync_quota_after_token_refresh` |

Cap `RATE_LIMITS["trial"]["credits"]` = 300 stays an integer
table value. Live **used** is the float.

## Inventory

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

### 3. ~~Two clocks, two hosts — easy to mix~~ — solved

**Already in code** (`bulk.py` `parse_farm_entry`, quota
`reset_at`, `auth.py` PAT fallback). grok-farm-modular puts
both clocks in one `tokens` object; import splits them:

| Farm field | Blob | Meaning |
|------------|------|---------|
| `tokens.expires_at` / `expires_in` | `expiresAt` | Job-token TTL (~24 h) |
| `tokens.pro_trial_*_at` | `proTrialStartAt` / `proTrialEndAt` | Credit window (~14 d) |
| `tokens.checked_quota` / `quota_remaining` / `is_quota_exceeded` | `farmQuota*` | Credit floor (item 6) |
| `tokens.personal_token` | `personalToken` | Re-exchange if refresh is late |
| Chat `api3` COSY | not this GET | Usage only if proxied |

Bar `reset_at` = API trial `expiresAt`, else `proTrialEndAt`.
Never blob `expiresAt`. Do not persist `password`, `proxy`,
`claim_status`, `claim_detail`.

Chat that never hits 9router still lags `usage_history`. Item 5
covers idle imports (dev→prod, IDE-only) on the next real
job-token refresh.

### 4. ~~Docs disagree with code~~ — solved

**Fixed 2026-09-02.** Quota design header is **approved**.
§2 list path, full-float credits, and `observe_complete` floor
increment match `quota.py` / `FLOW.md`.

### 5. ~~GET usage after a real job-token refresh~~ — solved

**Fixed 2026-09-02.** After a **successful** token recover
(`jobToken/refresh` or PAT re-exchange) in
`refresh_all_qoder_connections` / `try_refresh_connection`,
GET `quota/usage` with the new Bearer and write `quota_cache`
(`max` with local credits, full float). Covers idle imports
(dev→prod) and chats that never hit this 9router.

Do **not** GET usage when the refresh cycle skips a still-fresh
token. Tracker ticks already do not poll. GET failure does not
roll back the token refresh.

Already exists, not this item: operator card refresh is
`GET /usage/{id}?force=true`. In-use connections may also
re-poll on `/usage` after 15 min.

### 6. ~~Import with credits already used~~ — solved

**Fixed 2026-09-02.** `observe_complete` no longer sets
`used = sum(9router credits)`.

1. Cache exists: `cache.used + this chat` (full float).
2. Cache empty + blob `farmQuota*`: farm used + this chat.
3. Cache empty, no farm: **one** GET `quota/usage`, then
   `max(API, local)`. GET failure does not seed a local-only
   bar. Later chats hit (1) and do not GET again.

Do not GET usage on every chat. Idle imports without a chat
are covered by item 5 on the next real token refresh.

## Suggested order

1. ~~Gate job-token background refresh on `expiresAt`.~~ done.
2. ~~Stop list `GET /quota` from calling Qoder `fetch()`.~~ done.
3. ~~Item 6: `observe_complete` increment + farm floor + one
   GET on first chat if no cache/farm.~~ done.
4. ~~Item 5: GET `quota/usage` after a real token recover.~~
   done.
5. ~~Align quota design header status if still marked draft.~~
   done.
6. ~~Item 3: split farm job-token vs trial clocks.~~ already
   in `bulk.py`.

## Out of scope until asked

- COSY signing, WAF encode, device OAuth, catalog ids
- Other providers’ quota handlers
- Fake UI / hiding the 60 s countdown
