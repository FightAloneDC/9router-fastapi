# OpenRouter Provider Flow

`https://openrouter.ai/api/v1` — aggregator (vendor/model ids, Bearer).
Free-variant limits (`:free` suffix) are **per egress IP**, not per
API key. Paid (non-`:free`) models have **no** OpenRouter request cap.

OpenRouter success responses **omit** `X-RateLimit-*`. Those headers
appear on **429** (and sometimes only there). Remaining therefore
cannot come from a successful playground/`/chat` call alone.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, catalog flag, `RATE_LIMITS` by accountType |
| `handler.py` | Extra headers + TTS via chat completions |
| `models.py` | `GET /models` parsing |
| `quota.py` | IP-scoped caps, local log count, 429 overlay |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID          = openrouter
ALIAS                = openrouter
BASE_URL             = https://openrouter.ai/api/v1
CATEGORY             = freeTier
MODEL_CATALOG_TABLE  = True
AUTH                 = Bearer apiKey
```

`RATE_LIMITS` (docs 2026):

```
free       rpm=20  rpd=50     (< $10 lifetime credits)
payg       rpm=20  rpd=1000   (≥ $10 lifetime credits)
subscribe  rpm=20  rpd=1000
```

Connection `data.accountType` selects the row (`free` default).

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="openrouter/meta-llama/...:free"
  → provider openrouter
  → Bearer + HTTP-Referer / X-Title (handler extra headers)
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response (only writes cache if X-RateLimit-Limit)
  → stream or JSON to client
```

`/chat` and playground send `X-9Router-Purpose: test-chat` (proxy
usage flag, not quota).

## Models

Shared `provider_models` table. Prefix overlay via `provider_aliases`
(or config `ALIAS`). Custom models supported.

Strip `openrouter/` only when the remainder still contains `/`
(keep `openrouter/free`).

## Quota (`quota.py`)

`USES_UPSTREAM = False`.

### Used (success path)

Count `usage_history` on this host:

- **RPD** — `provider=openrouter` and `model LIKE '%:free'` since UTC
  midnight
- **RPM** — same filter, last 60 seconds

All OpenRouter connections share this count (one egress IP from the
9Router process, unless an outbound proxy actually rotates IP).

Paid model ids (no `:free`) **do not** increment RPM/RPD.

### Remaining from 429

`X-RateLimit-Limit` / `Remaining` / `Reset` (ms). Overlay onto RPM or
RPD when the limit value matches. Snapshot also stored in `kv`
(`scope=quota-ip`, `key=openrouter`) so every connection sees the
same IP remaining.

### Fetch

Always recompute local used; take max(used) vs 429 cache. Do not
return a stale all-zero cache after chats.

## Implementation notes

- Rotating HTTP proxies: OpenRouter may split the 50 RPD per IP;
  this tracker still counts **one pool** (it does not see egress IP).
- `GET /api/v1/key` (credits) is **not** polled on tracker load
  (ban-risk / noise).
- UI: catalog `rateLimits` on `/providers/openrouter`.
