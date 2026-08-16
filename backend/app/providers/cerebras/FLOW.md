# Cerebras Provider Flow

`https://api.cerebras.ai/v1` — OpenAI-compatible LLM. Rate limits
are **per model at organization level** (not IP). Published Free
Trial vs Developer (payg) caps live on
`CerebrasConfig.RATE_LIMITS`. Live remaining comes from
`x-ratelimit-*` headers when Cerebras sends them (success or 429).

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS` |
| `models.py` | Shared header-auth `/models` parse |
| `quota.py` | Plan catalog seed + header observe + merge |
| `__init__.py` | Package marker |

No custom `handler.py` — `BaseProviderHandler` + Bearer.

## Constants (`config.py`)

```
PROVIDER_ID          = cerebras
ALIAS                = cb
BASE_URL             = https://api.cerebras.ai/v1
FORMAT               = openai
MODEL_CATALOG_TABLE  = True
AUTH                 = Bearer apiKey
```

`RATE_LIMITS` from inference-docs.cerebras.ai/support/rate-limits
(keys `free/<model>` and `payg/<model>`). Connection
`data.accountType` selects the plan (`free` default; `payg` /
`developer` / `subscribe` → payg). Developer has no TPH/TPD.
Exact org: cloud.cerebras.ai Limits. Enterprise is not in config.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="cb/gpt-oss-120b"
  → alias cb → provider cerebras
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response (writes cache if remaining headers)
  → JSON or SSE to client
```

## Models

Catalog rows in `provider_models`. Fetch / enable / disable follow
the OpenRouter-style table path.

## Quota (`quota.py`)

`USES_UPSTREAM = False` (cheap overlay of cache + published rows).

### Seed

`published_quota_rows(plan)` — Free Trial: one TPD bar per model
(`used` filled on fetch from local logs). Developer: one RPM bar
per model.

### Live

`fetch` counts this connection's `usage_history` (TPD = tokens
today UTC; RPM on Developer = requests in the last 60s). Bars
move after chat even when Cerebras omits rate-limit headers.

When headers include remaining requests or tokens (OpenAI names
or `*-minute` suffixes), they overlay RPM/TPM. TPD `used` stays
the local token sum. `merge_live_rows` keeps the rest of the
plan catalog.
