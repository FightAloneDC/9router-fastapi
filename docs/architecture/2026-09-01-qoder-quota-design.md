# Qoder quota tracker

Date: 2026-09-01
Status: **approved** (2026-09-02)
Provider: `qoder` (alias `qd`)
Folder: `backend/app/providers/qoder/`

Written from this vendor only: `quota.py`, `config.py`,
`constants.py`, `FLOW.md`, live response shape (verified
2026-08), and `docs/archives/qoder-docs/QODER_PROVIDER_DOC.md`.
Do not copy Groq / Alibaba / Command Code / OpenRouter quota UX.

## Problem

Quota Tracker for Qoder feels unfinished because there is no
architecture decision. `FLOW.md` only describes the GET. The
generic tracker UI then treats Qoder like every other card
(reset countdown, % bar, bulk-depleted) without saying what the
numbers mean.

This document is the missing design. It does **not** change COSY,
auth, or catalog.

## What Qoder actually publishes

Qoder does **not** publish RPM / TPM / per-model caps. Chat is
COSY-signed on `api3.qoder.sh` and does not send remaining-credit
headers. Balance lives on a **different host and auth**:

| Item | Value |
|------|-------|
| URL | `https://openapi.qoder.sh/api/v2/quota/usage` |
| Auth | `Authorization: Bearer <job token>` (not COSY) |
| Unit | credits (full float in JSON, `QuotaItem`, cache) |
| Window | `expiresAt` epoch-ms — trial / account end, **not** a daily reset |
| Cap (published) | `RATE_LIMITS["trial"]` = 300 credits, ~14 days |

Verified body (2026-08):

```json
{
  "userType": "personal_professional_trial",
  "usageType": "credits",
  "isQuotaExceeded": false,
  "expiresAt": 1787423063188,
  "userQuota": {
    "total": 300.0,
    "used": 43.0,
    "remaining": 257.0,
    "percentage": 85.67,
    "unit": "credits"
  }
}
```

A depleted sample used `"percentage": 1.0` with
`used == total`. That field is **not** a stable remaining%.

Chat 402 / pricing / quota envelopes still mark the connection
**exhausted** (`is_active=False`) on the proxy path. That is
health, not a second credit counter.

## Decisions

### 1. One live credit bar

`fetch()` returns **one** `QuotaItem`:

- `name` = `unit` title-cased (`Credits`)
- `used` / `total` / `remaining` from `userQuota`
- `remaining_percentage` from `_pct(used, total)` — **ignore**
  `userQuota.percentage`
- `reset_at` = ISO from `expiresAt` (trial/account expiry)
- `plan` = `userType`
- `limit_reached` = `isQuotaExceeded` OR `remaining <= 0`

No per-model table. No `detail=models`. No RPM/TPM rows. Provider
Detail already shows the published 300 / 14-day note; the tracker
is the **live** bar.

### 2. List path reads cache; live GET is `/usage`

`USES_UPSTREAM = True`. Quota Tracker auto-refresh (60s) is
`GET /quota` and serves `quota_cache`. It does **not** call
`fetch()` per visible Qoder row. Chat `observe_complete` adds
this chat's credits to a floor (`quota_cache` / `farmQuota*` /
one GET on first chat). Empty cache is also filled by
`GET /usage/{id}` (`CACHE_MIN_AGE_S` 15 min, or `force=true`).

`fetch()` still GETs `quota/usage` with the job token and
takes max(API used, local `usage_history` credit sum).

After each proxied chat, `observe_complete` adds this chat's
`usage_history.tokens.credits` (SSE `usage.credits`, verified
2026-09-01) onto that floor — it does not replace the bar
with the 9router sum. `fetch()` takes max(live API used, that
local sum). `observe_response` stays a no-op — no
remaining-credit headers, and stream headers arrive too
early.

### 3. Trust live `total`; fallback only when missing

If `userQuota.total` is missing or 0, use
`RATE_LIMITS["trial"]["credits"]` (300). If upstream sends a
different total (other plan), **keep it**. Do not clamp every
account to 300.

Do **not** seed fake `0 / 300` bars into `quota_cache` for
accounts that have never been fetched. Empty until the first
`GET /usage/{id}` (or `observe_complete` after a proxied chat)
is correct; inventing a full trial hides already-depleted idle
accounts.

A grok-farm-modular **last check** is not a fake seed. See §7.

### 4. `reset_at` is expiry, not RPD

The generic “Expiring first” / countdown UI will show the trial
end date. That is intended. Do not invent a daily reset. Do not
relabel the bar “RPD”.

### 5. Credits stay full float

Qoder chat `usage.credits` / `original_credits` and quota API
`userQuota.used` / `remaining` / `total` MUST stay full floats
in Python, `quota_cache`, and JSON. Never `int()` or `round()`
there. Shared `QuotaItem.used` / `total` / `remaining` are
`float` so Pydantic does not truncate.

Tracker UI may show 2 decimal places (`toFixed(2)`). That is
display only. `% left` may still floor — percent, not credit.

### 6. Proxy exhaust vs tracker

| Signal | Where | Meaning |
|--------|-------|---------|
| `limit_reached` | quota API | credits gone or `isQuotaExceeded` |
| `is_active=False` (402) | proxy | chat exhausted |

Do not write credit remaining from a 402 body. After a proxy
exhaust, the tracker may still show the last cached bar until
the next poll or `force=true`. Inactive filter + Provider Detail
re-enable remain the operator tools.

`observe_response` stays a no-op (no credit remaining headers
on chat). Live credit from the chat is SSE `usage.credits`,
stored on `usage_history.tokens` and applied in
`observe_complete`.

### 7. grok-farm-modular snapshot (optional)

Bulk import is the farm JSON. Two clocks in one entry must not
be mixed:

| Farm field | Meaning | Connection blob |
|------------|---------|-----------------|
| `tokens.expires_at` / `expires_in` | Job-token TTL (~86400s) | `expiresAt` (OAuth) |
| `tokens.pro_trial_start_at` | Trial window start | `proTrialStartAt` |
| `tokens.pro_trial_end_at` | Trial window end | `proTrialEndAt` |
| `tokens.checked_quota` (else root) | Last known credit cap | `farmQuotaTotal` |
| `tokens.quota_remaining` | Last known remaining | `farmQuotaRemaining` |
| `tokens.is_quota_exceeded` | Last known exhaust | `farmQuotaExceeded` |
| `tokens.userType` / `plan` | Plan labels | `userType` / `plan` |
| `tokens.personal_token` | PAT for late `jobToken/exchange` | `personalToken` |

Do **not** persist `password`, `proxy`, `claim_status`, or
`claim_detail`. **Do** persist `personalToken` when the farm
entry has `tokens.personal_token` — job tokens die in a day.

Tracker:

1. Live `GET quota/usage` wins for used/remaining/`userType`.
2. `reset_at` = API `expiresAt`, else blob `proTrialEndAt`.
   Never blob `expiresAt` (that is the job token).
3. If the GET fails, show the farm snapshot when any of those
   optional keys exist. Credits-only missing + trial end still
   yields a bar whose `reset_at` is the trial end (no invented
   `0/300` remaining).

`quota_cache` is still written on first successful
`GET /usage/{id}` (shared router). Import does not insert cache
rows.

## Out of scope

- Other providers
- COSY / device / PAT / refresh
- Catalog / `provider_models`
- Frontend-only copy changes (unless a later UI task)
- Inventing RPM/TPM or a model-details modal

## Remaining after §7

None. Open-problems inventory is closed (2026-09-02), including
GET `quota/usage` after a real job-token refresh.
