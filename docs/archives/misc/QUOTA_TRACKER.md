# Quota Tracker — Mechanism & Flow Documentation

## Overview

The Quota Tracker monitors API usage limits for provider
connections. Each supported provider ships its own usage API
handler; the system fetches quota data per connection and
displays it in a unified dashboard at `/quota-tracker`.

Upstream polling is deliberately throttled: most connections are
farmed accounts, and aggressive balance polling risks bans. See
[Polling Policy](#polling-policy-ban-risk-reduction).

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend                               │
│                                                               │
│  QuotaTrackerPage                                             │
│    ├── fetchData() ─────────── GET /quota ─────────┐          │
│    ├── auto-refresh (30s/60s/180s)                 │          │
│    ├── localStorage cache (5 min TTL)              │          │
│    └── per-connection refresh ─ GET /usage/{id} ──┐│          │
└───────────────────────────────────────────────────┘│──────────┘
                                                     │
┌────────────────────────────────────────────────────┘──────────┐
│                        Backend                                 │
│                                                                │
│  GET /quota                                                    │
│    └── List connections of SUPPORTED providers only            │
│        (filtered by quota handler registry)                    │
│                                                                │
│  GET /usage/{connectionId}[?force=true]                        │
│    ├── 1. Get connection from DB                               │
│    ├── 2. Serve quota_cache table row if usable (not force)    │
│    ├── 3. Refresh OAuth token if expired                       │
│    ├── 4. Call provider usage handler (PS hook) ──────────────┐│
│    └── 5. Upsert result into quota_cache, return it           ││
│                                                               ││
│  Usage handlers (PS rule — one per provider folder):          ││
│    providers/github/quota.py  ── GitHubUsageHandler           ││
│    providers/claude/quota.py  ── ClaudeUsageHandler           ││
│    providers/codex/quota.py   ── CodexUsageHandler            ││
│    providers/kiro/quota.py    ── KiroUsageHandler             ││
│    providers/qoder/quota.py   ── QoderUsageHandler ◄──────────┘│
│                                                                │
│  services/quota/                                               │
│    ├── base.py        ── BaseUsageHandler + shared schemas     │
│    └── __init__.py    ── discovery registry (auto-imports      │
│                           providers/<name>/quota.py)           │
└────────────────────────────────────────────────────────────────┘
```

## PS Rule — Handlers Live in Provider Folders

Provider-specific quota logic (endpoint URL, auth headers,
response parsing) MUST live in
`backend/app/providers/<provider>/quota.py`, never in a global
service file.

`services/quota/__init__.py` is a generic registry with zero
hardcoded provider names. At import time it scans
`app/providers/` (pkgutil), tries to import
`app.providers.<name>.quota` (importlib), and registers any
`BaseUsageHandler` subclass it finds there — the same discovery
idiom as `services/catalog.py`.

**Adding quota support for a new provider:**

1. Create `backend/app/providers/<name>/quota.py`.
2. Define one class extending `BaseUsageHandler`
   (set `PROVIDER_ID`, implement `fetch()`).
3. Done — the registry picks it up; `GET /quota` and the UI
   dropdown include it automatically. No global file edits.

Optional hooks:

- `USES_UPSTREAM = False` — handler derives usage from local
  state; the router skips quota_cache for it.
- `observe_response(db, connection_id, headers)` — called by
  the proxy on every successful upstream response (dispatched
  via `observe_upstream_response()`), for providers that expose
  quota signals in response headers.

## Endpoints

### `GET /quota`

Returns connections **only for providers that have a usage
handler** (`supported_providers()`), each with empty `quotas`.
Real data is fetched per connection via `/usage/{id}`. The
frontend derives both the card list and the provider filter
dropdown from this response, so unsupported providers never
appear on the quota tracker page.

### `GET /usage/{connectionId}`

1. Validate id is a UUID (rejects stray paths like
   `/usage/stream` hitting the param route).
2. Look up the connection; reject providers without a handler
   with an informational message.
3. If `force` is false, serve the `quota_cache` row when usable
   (see polling policy below).
4. Otherwise: extract access token from the data blob, refresh
   expired OAuth tokens, call the provider handler, upsert the
   result into `quota_cache`, and return it.

`force=true` always polls upstream (used by the card refresh
button).

### `GET /usage/stream` (related)

SSE endpoint for real-time active-request stats. Registered in
`main.py` BEFORE the quota router — otherwise
`/usage/{connection_id}` shadows it (connection_id="stream").

## Cache: `quota_cache` Table

Quota balances are cached per connection in a dedicated table
(alembic `9a3d69805d5d`), NOT in the connection data blob —
with thousands of farmed accounts per provider, blob storage
would bloat every connection row.

```
quota_cache
├── connection_id   UUID PK, FK → provider_connections (CASCADE)
├── plan            VARCHAR(100), nullable
├── quotas          TEXT — JSON list of QuotaItem
├── limit_reached   BOOLEAN
└── fetched_at      TIMESTAMPTZ
```

`_store_quota_cache()` upserts by `connection_id` after every
successful upstream fetch.

Legacy note: an earlier implementation stored `quotaCache` in
the connection data blob. Existing blobs were migrated once by
`tests/_backfill_quota_cache.py` (idempotent, re-runnable). The
blob field is dead data — never read anymore.

## Polling Policy (Ban-Risk Reduction)

Constants in `routers/quota.py`:

- `CACHE_MIN_AGE_S = 900` — cache younger than 15 min is always
  served, no upstream call.
- `IN_USE_WINDOW_S = 3600` — a connection counts as "in use" if
  it served a proxied request within the last hour
  (`lastUsedAt` in the data blob).

Decision (`_quota_cache_usable`):

| Cache age | Connection in use | Result |
|-----------|-------------------|--------|
| < 15 min  | any               | serve cache |
| ≥ 15 min  | idle (or never)   | serve cache — never re-poll |
| ≥ 15 min  | in use            | re-poll upstream |

So idle accounts are polled at most once (on first fetch), and
active accounts at most every 15 minutes.

## Provider-Specific Usage APIs

### GitHub Copilot
```
Endpoint: GET https://api.github.com/copilot_internal/user
Auth: GitHub OAuth token
Headers: Authorization: token {accessToken}

Response (paid): copilot_plan + quota_snapshots
  { chat, completions, premium_interactions } with
  entitlement/remaining/unlimited + quota_reset_date
Response (free): monthly_quotas / limited_user_quotas +
  limited_user_reset_date
```

### Claude (Anthropic)
```
Endpoint: GET https://api.anthropic.com/v1/usage
Auth: OAuth Bearer token
Headers: anthropic-beta: oauth-2025-04-20

Response: five_hour / seven_day / seven_day_sonnet /
  seven_day_opus, each { utilization, resets_at }.
utilization = percent USED (45 → 55% remaining).
```

### Codex (OpenAI)
```
Endpoint: GET https://api.openai.com/v1/usage
Auth: OAuth Bearer token

Response: plan_type + rate_limit.{primary_window,
  secondary_window} with used_percent + reset_at.
used_percent = percent USED.
```

### Kiro (AWS CodeWhisperer)
```
Endpoint: GET https://codewhisperer.us-east-1.amazonaws.com/getUsageLimits
Auth: OAuth Bearer token or API key
Headers: x-amz-user-agent: aws-sdk-js/1.0.0 KiroIDE

Response: subscriptionInfo + usageBreakdownList[] with
  resourceType, currentUsageWithPrecision,
  usageLimitWithPrecision, nextDateReset.
```

### Grok CLI (Grok Build) — local-state handler
```
No upstream polling (USES_UPSTREAM=False). xAI exposes no
balance API for free-tier accounts, so quota data is assembled
from signals piggybacked on real traffic:

1. Local token accumulation (the "used" counter). Sum of
   today's (UTC) prompt+completion tokens from usage_history
   (written by the proxy per request). This is the only usage
   signal that moves: the upstream X-Ratelimit-Remaining-*
   headers arrive static (always full) and are not trusted for
   usage. The "Daily free (grok-4.5)" bar advances with every
   proxied chat.

2. Rate-limit headers (limit discovery). Every successful chat
   response from cli-chat-proxy carries:
       X-Ratelimit-Limit-Tokens / X-Ratelimit-Remaining-Tokens
       X-Ratelimit-Limit-Requests / X-Ratelimit-Remaining-Requests
   The proxy dispatches response headers through the PS hook
   observe_upstream_response() → GrokCliUsageHandler
   .observe_response(), which snapshots them into quota_cache
   (one row per connection, valid for the UTC day). fetch()
   uses the snapshot only for the account's token LIMIT and the
   "Requests" bar.

3. Recorded upstream errors. The proxy cooldown path stores
   errorCode / lastError / testStatus in the connection data
   blob (mark_connection_unavailable writes them,
   clear_connection_error clears them on success). Classified
   with the farm resort contract
   (grok-farm-modular cli/nine_router/health.py):

     401 or invalid_grant/revoked      → dead (re-authorize)
     402/403 or spending/balance/
       exhausted/quota keywords        → exhausted, limit_reached
     429                               → rate-limited (cooldown)

   The free-usage 429 body carries authoritative numbers —
   "tokens (actual/limit): 539793/500000" — which calibrate
   both used and limit for that connection.

Research notes (grok-farm-modular, verified 2026-08):
- Free tier comes from x.ai and is limited to grok-4.5.
  Grok (grok.com) has no free plan — grok-build 402s on free
  accounts by design (model gating, not exhaustion).
- Daily allowance: 2M tokens/day during the first promo
  period, later reduced to 1M/day (matches the observed
  X-Ratelimit-Limit-Tokens: 1000000). Resets on a rolling
  24-hour window.
- Enforcement observed 2026-08-09: one farmed account 429'd
  at an actual 500K limit while its headers still claimed 1M —
  the real limit appears account-specific; the 429 body is the
  only authoritative source (see point 3).
```

### Qoder (verified 2026-08)
```
Endpoint: QODER_QUOTA_USAGE_URL (providers/qoder/constants.py)
Auth: OAuth Bearer token

Response:
{
  "userType": "personal_professional_trial",
  "usageType": "credits",
  "isQuotaExceeded": false,
  "expiresAt": 1787423063188,
  "userQuota": { "total": 300.0, "used": 43.0,
                 "remaining": 257.0, "percentage": 85.67,
                 "unit": "credits" }
}

limit_reached = isQuotaExceeded OR remaining <= 0
reset_at derived from expiresAt (epoch ms)
```

## Standardized Quota Schema

Defined in `services/quota/base.py` (pydantic):

```python
class QuotaItem(BaseModel):
    name: str
    used: int = 0
    total: int = 0
    remaining: Optional[int] = None
    remaining_percentage: float = 100.0
    reset_at: Optional[str] = None      # ISO 8601
    unlimited: bool = False

class UsageResponse(BaseModel):
    plan: Optional[str] = None
    quotas: list[QuotaItem] = []
    message: Optional[str] = None       # info/error, no quotas
    limit_reached: bool = False
```

## Supported Providers (current)

| Provider | Auth | Handler | Quotas |
|----------|------|---------|--------|
| GitHub | OAuth | providers/github/quota.py | chat, completions, premium |
| Claude | OAuth | providers/claude/quota.py | 5h session, 7d weekly (+ per-model) |
| Codex | OAuth | providers/codex/quota.py | session, weekly |
| Kiro | OAuth/API key | providers/kiro/quota.py | agentic requests etc. |
| Qoder | OAuth | providers/qoder/quota.py | credits |

Any other provider returns a "Usage tracking not supported"
message and is hidden from the quota tracker page.

## Frontend Features

### Fetch flow
1. Page load → localStorage cache (5 min TTL) shown instantly if
   fresh; fresh data fetched in background regardless.
2. `GET /quota` → render cards.
3. `GET /usage/{id}` per ACTIVE connection, batched 5 at a time.
4. Manual card refresh uses `force=true`.

### Filtering & sorting
- Provider filter (dropdown shown only when >1 provider type)
- Status filter: All / Active / Inactive
- Sort: default / % remaining low→high / high→low
- "Expiring first": earliest reset time
- Search by connection name or provider

### Connection management
- Toggle active/inactive (optimistic update, rollback on error)
- Edit connection name
- Delete with confirmation
- Bulk: disable depleted (≤5% remaining), enable all inactive

### Display
- Emoji indicators: 🟢 (>70%), 🟡 (30–70%), 🔴 (<30%)
- Reset time: countdown + "Today, 12:00 PM" style labels
- Provider logos from `/providers/{id}.png` with initials
  fallback
- Pagination: 10/20/50 per page

## Key Files

```
backend/app/routers/quota.py          # /quota + /usage/{id}, cache policy
backend/app/models/quota_cache.py     # QuotaCache table model
backend/app/services/quota/base.py    # BaseUsageHandler + schemas
backend/app/services/quota/__init__.py # discovery registry
backend/app/providers/<name>/quota.py # per-provider usage handler (PS)
backend/alembic/versions/9a3d69805d5d_add_quota_cache_table.py
tests/_backfill_quota_cache.py        # one-time blob → table migration
frontend/src/pages/QuotaTrackerPage.jsx
frontend/src/api/quota.js

# Original Next.js reference (flow inspiration only):
# _reference/ → services/usage/*, api/usage/[connectionId]/*
```
