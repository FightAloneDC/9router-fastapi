# Cohere Provider Flow

`https://api.cohere.com/compatibility/v1` — OpenAI-compatible Chat /
embeddings. Native rerank uses `https://api.cohere.com/v1/rerank`.
Chat rate limits are **per model**; rerank/embed are **per
endpoint**. Trial (`accountType=free`) also has **1000 API calls /
month** across all endpoints.

Docs: https://docs.cohere.com/docs/rate-limits

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS`, notice |
| `handler.py` | Native `execute_rerank` |
| `models.py` | Shared header-auth `/models` parse |
| `quota.py` | Summary tracker + on-demand model detail |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID          = cohere
ALIAS                = co
BASE_URL             = https://api.cohere.com/compatibility/v1
CATEGORY             = freeTier
FORMAT               = openai (compat)
MODEL_CATALOG_TABLE  = True
AUTH                 = Bearer apiKey
```

`RATE_LIMITS` keys are **exact** catalog / upstream model ids
(same rule as Groq and `alims-intl`), prefixed by
`accountType` (`free` / `payg` / `subscribe`):

```
free/command-a-reasoning-08-2025  → rpm 20
payg/command-a-03-2025            → rpm 500
free/rerank-v4.0-pro              → rpm 10
free/embed-v4.0                   → ipm 2000
free/_monthly                     → calls 1000
```

Do not invent marketing names (`command-a-reasoning`) that are
absent from `provider_models` / `usage_history`.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="co/command-r"
  → alias co → provider cohere, strip co/ for upstream id
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response("cohere", …) when headers exist
  → JSON or SSE to client
```

## Models

Catalog rows in `provider_models` (`MODEL_CATALOG_TABLE`). Fetch /
enable / disable follow the OpenRouter-style table path. Do not
write catalogs into connection `data.models`.

## Quota (`quota.py`)

`USES_UPSTREAM = False`.

### List / refresh (`fetch`)

Small summary only (persisted when the router caches):

1. `requests (last 60s)` — local `usage_history`, unlimited
2. `tokens (last 60s)` — local, unlimited
3. If `free`: `calls (month)` used vs 1000 since UTC month start

### Model details (`fetch_model_details`)

`GET /usage/{id}?detail=models` — for each published catalog id:

- `{id} requests (RPM)` / `inputs (IPM)` — **last 60s** vs cap
- `{id} requests (today)` / `inputs (today)` — UTC-day local
  count, unlimited (so usage remains visible after the minute
  window)

**Not** written to `quota_cache`.

UI: Quota Tracker ListTree button for `cohere` (same as
`alims-intl`).

### `observe_response`

Writes only when remaining-request headers exist. Merges last-model
live RPM onto summary bars; never seeds the full catalog.

## Rerank

`CohereHandler.execute_rerank` posts to the native
`/v1/rerank` host (not compatibility mode).

## Implementation notes

- Strip only alias `co/` or `cohere/`.
- `payg` and `subscribe` share published production caps.
- Embed IPM `used` uses local request count as a proxy (Cohere
  docs meter inputs/min; we do not count batch size here).
- Exact org/key overrides live in the Cohere dashboard.
