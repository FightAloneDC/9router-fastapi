# NVIDIA NIM Provider Flow

`https://integrate.api.nvidia.com/v1` — OpenAI-compatible NIM
(free Developer Program keys). Rate limit is **per API key**, not
per IP. NVIDIA publishes **~40 RPM** for the free serverless
endpoint; there is **no** per-model table and **no** usage API.

Success and 429 bodies often omit `X-RateLimit-*` and
`Retry-After`. Remaining cannot come from a successful chat alone.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, catalog flag, `RATE_LIMITS` (free RPM) |
| `handler.py` | Validate `/models`; TTS `/audio/speech`; STT multipart |
| `models.py` | Shared header-auth `/models` parse |
| `quota.py` | Local RPM count + optional header overlay |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID  = nvidia
ALIAS        = nvidia
BASE_URL     = https://integrate.api.nvidia.com/v1
CATEGORY     = freeTier
FORMAT       = openai
AUTH         = Bearer apiKey
MODEL_CATALOG_TABLE = True
```

`RATE_LIMITS` (docs / NVIDIA forums, free NIM):

```
free  rpm=40
```

No RPD in NVIDIA docs. Actual 429s also depend on model, traffic,
and concurrency. Paid/self-hosted NIM is out of scope here.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="nvidia/<vendor>/<id>"
  → alias nvidia → provider nvidia
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response (writes cache only if rate-limit
     headers exist)
  → JSON or SSE to client
```

Playground defaults to non-stream; `/chat` streams. Both paths
already call `observe_upstream_response`.

## Models

Catalog rows in `provider_models` (`MODEL_CATALOG_TABLE`). Fetch /
enable / disable follow the OpenRouter-style table path. TTS/STT/
embedding ids also use `MODEL_TYPE_OVERRIDES` plus heuristics.

## Quota (`quota.py`)

`USES_UPSTREAM = False`.

### Used (success path)

Count `usage_history` for `provider=nvidia` (this connection):

- **today** — since UTC midnight (no published daily cap; shown
  as used / ∞ so the tracker is not empty after a chat)
- **RPM** — last 60 seconds vs config 40

Connection id match is hyphen-insensitive. NVIDIA omits
rate-limit headers on success, so logs are the source of
`used`, not `observe_response`.

### Live headers (rare)

If NVIDIA sends them (success or 429):

```
x-ratelimit-limit / x-ratelimit-limit-requests
x-ratelimit-remaining / x-ratelimit-remaining-requests
x-ratelimit-reset / x-ratelimit-reset-requests / retry-after
```

`observe_response` no-ops when those headers are missing. It
caches rows named `NIM requests (last 60s / RPM)` (same
merge key as the local RPM bar) and, when the header limit
differs from config rpm, `NIM requests (header)`.

`fetch` overlays a fresh cache (`fetched_at` ≤ 90 s) onto
local counts: matching names take `max(local used, cached
used)`; leftover `NIM requests*` rows are appended. A stale
or timestamp-less cache is ignored so a rare 429 snapshot
cannot pin the RPM bar. No headers (the common case) →
local counts only.
