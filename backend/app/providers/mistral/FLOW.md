# Mistral Provider Flow

Written from `backend/app/providers/mistral/` only.

`MistralConfig.BASE_URL` is `https://api.mistral.ai/v1`. Auth is
Bearer `data.apiKey`. Chat bodies are sanitized before upstream.
Bulk farm import is email + api_key. Catalog is
`provider_models`. Quota `used` is local `usage_history` for this
connection. Public docs do not publish numeric RPS/TPM tables
(console Limits is exact; org-level).

## Files

| File | Role |
|------|------|
| `config.py` | Identity, catalog flag, empty `RATE_LIMITS`, embed override, bulk flags |
| `handler.py` | sanitize request; capability-driven reasoning; unwrap/SSE flatten; embeddings: drop OpenAI `dimensions` (mistral-embed fixed 1024); map → `output_dimension` for codestral-embed; no farm rotate on 422/429/labs |
| `transform.py` | Drop client-only fields; reasoning via `capabilities.reasoning` cache; clamp effort to none|high; flatten thinking/text content for OpenAI clients |
| `models.py` | `fetch_models` + cache `capabilities.reasoning`; upstream `type: base` is ignored — kinds come from overrides/infer |

| `bulk.py` | Farm JSON → email + `token_data.apiKey` |
| `quota.py` | `MistralUsageHandler`: local logs + optional headers |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_NAME        = Mistral
PROVIDER_ID          = mistral
ALIAS                = mi
BASE_URL             = https://api.mistral.ai/v1
SERVICE_KINDS        = llm, imageToText, embedding
MODEL_CATALOG_TABLE  = True
SUPPORTS_BULK_IMPORT = True
BULK_IMPORT_FORMAT   = farm-json
MODEL_TYPE_OVERRIDES = mistral-embed(+variants),
                       codestral-embed(+variants) → embedding
RATE_LIMITS          = free: {}, scale: {}
```

Plan from `data.accountType` (`quota._plan`): `scale` / `payg` /
`subscribe` / `developer` → `scale`; else `free`. Caps dicts are
empty on purpose.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="mi/mistral-small-latest"
  → alias mi → provider mistral
  → MistralHandler.build_request_body
       sanitize_mistral_chat_body (drop max_context_size,
       max_context, context_length, store — also inside
       extra_body; map developer→system; reasoning* from
       capabilities cache: True→clamp none|high, False→drop,
       None→keep+clamp)
  → upstream chat/completions
  ← if 400 reasoning rejection (code 3051, "reasoning_effort is not
       enabled", "reasoning is not enabled") or 422 with reasoning*
       still present and the capability cache does not say supported:
       strip → retry same connection once; every 400 rejection sets
       the capability cache to False. Models that accept reasoning
       never hit these — not a global disable.
  ← Magistral may return content as thinking+text parts;
       unwrap / SSE flatten keeps type:text only for stream deltas
       (drops thinking deltas; does not touch string content —
       avoids cutting answers or leaking the plan into Pi);
       non-stream thinking-only content is promoted to text
  → Bearer data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response → MistralUsageHandler.observe_response
  → JSON or SSE
  → usage_history (prompt_tokens + completion_tokens)
```

`observe_response` no-ops unless minute limit/remaining headers
are integers (`*-req-minute`, `*-tokens-minute`). Bars are labeled
**RPM/TPM (per minute)**; `reset_at` prefers `x-ratelimit-reset` /
`retry-after` headers, falling back to next minute (not a cryptic
"(header)" + N/A). Stale header overlays older than 90s are ignored
on fetch so exhausted snapshots do not stick forever.

### Fallback (PS — do not rotate the farm)

`MistralHandler.should_fallback_on_error` returns **False** for:

- Labs models not enabled (`labs_not_enabled` / "is a Labs model"
  / bare "labs model"; also HTTP **403** containing "labs" or
  "not enabled")
- HTTP **422** (body rejected; same body on the next key fails)
- HTTP **429** / `rate_limited` / "rate limit" text (do not burn
  the farm)

Chat/messages/responses also support one same-connection body
rewrite via `rewrite_body_after_error` before surfacing a 422.

Chat/messages/responses/embeddings/images/audio also abort the
fallback loop when the client disconnects (chat family), and all
stop after `MAX_FALLBACK_ATTEMPTS` (5) — pool size does not
imply unbounded rotate.

## Models

`MODEL_CATALOG_TABLE` is True. Rows in `provider_models`.
`models.fetch_models(api_key)` GETs `/models` with header auth and
caches each id's `capabilities.reasoning` in-process (no model-id
allowlist).

## Bulk (`bulk.py`)

Farm entry must be an object with `api_key`/`apiKey` and `email`.
Dedup key is lowercased email. `token_data` stores `apiKey`,
`email`, `displayName`, `providerSpecificData.authMethod =
bulk_import`.

## Quota (`quota.py`)

`PROVIDER_ID = "mistral"`. `USES_UPSTREAM = False` (no admin
rate-limit poll).

### Fetch

`_usage_totals` for `provider = mistral` and this connection
(UUID dashes ignored): count + sum(prompt + completion).

- today UTC midnight → **Mistral requests (today)** and
  **Mistral tokens (today)** (`total=0`, unlimited)
- last 60s → **Mistral requests (last 60s)** (unlimited)

Cached header bars with other names are appended only if they pass
the live-header-bar name filter ("(header)" / "per minute" /
"mistral rpm" / "mistral tpm"). `plan` is free|scale.
`limit_reached` only if a non-unlimited bar has remaining 0.

### Observe

If live headers exist, store request and/or token header bars in
`quota_cache`.
