# Cerebras Provider Flow

Written from `backend/app/providers/cerebras/` only.

`CerebrasConfig.BASE_URL` is `https://api.cerebras.ai/v1`. Format
defaults to OpenAI (`BaseProviderConfig.FORMAT`). Auth is Bearer
`data.apiKey`. Limits are per organization and per model (not IP).
Published Free Trial vs Developer (payg) caps live on
`CerebrasConfig.RATE_LIMITS`. Tracker `used` on fetch comes from
local `usage_history`. Headers overlay only when Cerebras sends
remaining counts.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS`, UI notice |
| `models.py` | `fetch_models` via `fetch_models_header_auth`; parse `data` |
| `quota.py` | `CerebrasUsageHandler`: local logs + optional header cache |
| `__init__.py` | Package marker |

No `handler.py` — `BaseProviderHandler` + Bearer.

## Constants (`config.py`)

```
PROVIDER_NAME        = Cerebras
PROVIDER_ID          = cerebras
ALIAS                = cb
BASE_URL             = https://api.cerebras.ai/v1
SERVICE_KINDS        = ["llm"]
MODEL_CATALOG_TABLE  = True
FORMAT               = openai (base default)
AUTH                 = Bearer apiKey
```

`RATE_LIMITS` keys are `free/<model>` and `payg/<model>` for
`gpt-oss-120b`, `zai-glm-4.7`, `gemma-4-31b`. Free has rpm / tpm /
tph / tpd. Payg has rpm / tpm only.

Plan from connection `data.accountType` (`quota._plan`):
`payg` / `subscribe` / `developer` → `payg`; anything else →
`free`. Exact org caps: cloud.cerebras.ai Limits. Enterprise is
not in this table.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="cb/gpt-oss-120b"
  → alias cb → provider cerebras
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response → CerebrasUsageHandler.observe_response
  → JSON or SSE to client
  → usage_history row (prompt_tokens + completion_tokens)
```

`observe_response` is a no-op unless one of these remaining
headers is an integer:

```
x-ratelimit-remaining-requests
x-ratelimit-remaining-tokens
x-ratelimit-remaining-requests-minute
x-ratelimit-remaining-tokens-minute
```

Quota Tracker does **not** wait on those headers. `fetch` always
counts `usage_history`.

## Models

`MODEL_CATALOG_TABLE` is True. Rows live in `provider_models`.
`models.fetch_models(api_key)` GETs `/models` with header auth and
returns `response["data"]`.

## Quota (`quota.py`)

`CerebrasUsageHandler.PROVIDER_ID = "cerebras"`.
`USES_UPSTREAM = False` (router does not poll a Cerebras usage
API).

Prefix `cb/` is stripped only when the first segment is `cb`.

### Fetch (what the tracker shows)

1. `_usage_by_model` on this connection (`provider = cerebras`,
   UUID dashes ignored): tokens = sum(prompt + completion),
   requests = row count, grouped after `_strip_prefix`.
2. Window A: today UTC midnight → used for TPD.
   Window B: last 60 seconds → used for RPM.
3. `apply_local_usage(plan, today, last_min)`:
   - **free**: one `{model} tokens (TPD)` bar per catalog model
     (`used` = today's tokens, `total` = config `tpd`,
     `reset_at` = next UTC midnight).
   - **payg**: one `{model} requests (RPM)` bar
     (`used` = last-minute request count, `total` = config `rpm`,
     `reset_at` = now + 60s).
4. If `quota_cache` has JSON for this connection, matching bar
   names take `max(local used, cached used)`. Extra cached bars
   whose names contain `TPM` or `TPH` are appended.
5. `limit_reached` if any returned bar has `remaining <= 0` and
   is not unlimited.

### Observe (optional cache)

If remaining headers exist, `quotas_from_headers` builds RPM /
TPM / TPH / TPD for **that** model from config plus:

```
x-ratelimit-limit-requests[+ -minute]
x-ratelimit-remaining-requests[+ -minute]   → RPM remain
  (only if header limit is missing or equals config rpm)
x-ratelimit-limit-tokens[+ -minute]
x-ratelimit-remaining-tokens[+ -minute]     → TPM remain
x-ratelimit-reset-requests
x-ratelimit-reset-tokens[+ -minute]
```

TPH and TPD in that live set use config totals with remain =
total (`used=0`). `merge_live_rows` keeps other models' catalog
rows and replaces this model's prefix. Written to `quota_cache`
(`plan` = free|payg). `*-day` headers are not read.

### Seed helper

`published_quota_rows(plan)` is `used=0` TPD (free) or RPM
(payg). Used as the merge base when cache is empty, not as the
primary `fetch` path.
