# Groq Provider Flow

`https://api.groq.com/openai/v1` — OpenAI-compatible LLM / STT. Rate
limits are **per model at organization level** (not IP, not per key).
Published Developer-plan caps live on `GroqConfig.RATE_LIMITS`; live
remaining comes from Groq response headers on **every** chat (stream
and non-stream).

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS` |
| `handler.py` | Whisper STT multipart (`execute_stt`) |
| `models.py` | `/models` list parsing |
| `quota.py` | Catalog seed + header observe + merge |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID          = groq
ALIAS                = gq
BASE_URL             = https://api.groq.com/openai/v1
FORMAT               = openai
MODEL_CATALOG_TABLE  = True
AUTH                 = Bearer apiKey
```

`RATE_LIMITS` is the Developer-plan **base** table from Groq docs
(RPM / RPD / TPM / TPD; whisper ASH / ASD). Exact org caps:
`console.groq.com/settings/limits`. Free plan has **no** published
per-model table in docs.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="gq/openai/gpt-oss-120b"
  → alias gq → provider groq, strip prefix for upstream id
  → Bearer from connection data.apiKey
  → POST {BASE_URL}/chat/completions
  → observe_upstream_response("groq", connection_id, headers, model)
  → JSON or SSE to client
```

Playground defaults to **non-stream**; `/chat` uses **stream**. Both
paths must call `observe_upstream_response` (`shared._non_stream_response`
and `_stream_response`).

## Models

Catalog rows in `provider_models` (`MODEL_CATALOG_TABLE`). Fetch /
enable / disable follow the OpenRouter-style table path.

## Quota (`quota.py`)

### Seed (unused connection)

`published_quota_rows()` — one RPD bar per model from `RATE_LIMITS`
(`used=0`). Quota Tracker is not empty before the first chat.

### Live (after a chat)

Headers (always present on Groq success **and** 429):

```
x-ratelimit-limit-requests      → RPD
x-ratelimit-remaining-requests  → RPD
x-ratelimit-reset-requests      → duration (e.g. 2m59.56s) → ISO
x-ratelimit-limit-tokens        → TPM
x-ratelimit-remaining-tokens    → TPM
x-ratelimit-reset-tokens        → duration → ISO
```

`retry-after` only on HTTP 429.

RPM / TPD (and whisper ASH / ASD) are **config-only** — Groq does not
send remaining for those.

### Merge

`merge_live_rows` keeps the full catalog. The model that was just
used is replaced with RPM + RPD + TPM + TPD (or ASH/ASD) rows.
Other models stay as seed RPD bars. `overlay_live_on_published`
heals an old last-model-only cache on fetch.

`USES_UPSTREAM = False` — tracker calls `fetch()` on list load.

## Implementation notes

- Strip only alias `gq/`, never `groq/` (upstream ids like
  `groq/compound`).
- Org-level: all keys on the same Groq org share caps. Cache is still
  per connection; we do not merge across Groq connections.
- Header names are matched case-insensitively.
- UI: catalog `rateLimits` table on `/providers/groq`.
