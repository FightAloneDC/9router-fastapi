# Jina AI provider flow

Source of truth: files in this folder + official docs URL below.
Updated 2026-08-25 (unified kinds + quota tracking notes).

## Files

| File | Role |
|------|------|
| `config.py` | Identity, hosts, kinds, static maps, `RATE_LIMITS`, defaults |
| `models.py` | Live `GET /models` + synthetic search/reader from config |
| `handler.py` | Embed, rerank, search (`s.`), fetch (`r.`) |
| `quota.py` | Local free tokens + embed/rerank RPM/TPM |

**Audit — statics in `config.py`:** hosts, default models,
`WEB_CATALOG`, `RETURN_FORMAT_MAP`, `UI_TO_DOCS_PLAN`,
`RATE_LIMITS`, `LEGACY_IDS` belong only in `config.py`. Do not
scatter module-level maps in sibling files; open `config.py` when
values change.

**Audit — naming:** leading `_` = private to that module. Anything
imported from another file (config fields, `resolve_plan`,
`parse_response`, …) must be unprefixed.

## Identity

```
PROVIDER_NAME        = Jina AI
PROVIDER_ID          = jina-ai
ALIAS                = jina
BASE_URL             = https://api.jina.ai/v1
SEARCH_BASE_URL      = https://s.jina.ai
READER_BASE_URL      = https://r.jina.ai
SERVICE_KINDS        = embedding, rerank, webSearch, webFetch
MODEL_CATALOG_TABLE  = True
LEGACY_IDS           = jina-search, jina-reader, jinas, jinar
DEFAULT_EMBEDDING_MODEL = jina-embeddings-v3
DEFAULT_RERANK_MODEL = jina-reranker-v3.5
EXTRA_HEADERS        = Accept: application/json
```

One connection / one API key for all kinds. Do **not** split
search or reader into separate providers. Proxy alias map resolves
`LEGACY_IDS` → `jina-ai`.

## Official docs

https://docs.jina.ai/ (llms.txt), retrieved 2026-08-25.

- Embed + rerank: **500 RPM / 1M TPM** (premium **2k / 5M**).
- Search (s.jina.ai): **100 RPM** free / **1k** premium (no TPM).
- Reader (r.jina.ai): **500 RPM** free / **5k** premium (no TPM).
- Free **10M tokens** per new API key: `operator: 2026-08-25`
  (dashboard; shared across api/s/r hosts). Not on docs.jina.ai.

## Model catalog

1. Live `GET {BASE_URL}/models` — strip `jina-ai/` prefix; type
   from id / `output_modalities` (embed / rerank / llm).
2. Synthetic rows (no list-models on s/r): `search` (webSearch),
   `reader` (webFetch).

## Proxy paths

| Kind | Host | Wire |
|------|------|------|
| embedding | api.jina.ai | POST `/embeddings`; wrap string `input`; keep `dimensions`; `encoding_format`→`embedding_type` |
| rerank | api.jina.ai | POST `/rerank`; keep `top_n` |
| webSearch | s.jina.ai | POST `/`; body `q` (+ `gl`/`hl`/`num`); usage from `x-usage-tokens` / `meta.usage.tokens` |
| webFetch | r.jina.ai | GET `/{url}` + `X-Return-Format`; raw text body; tokens from `x-usage-tokens` |

Search/reader ignore connection `baseUrl` (that overrides api
host only). All three host strings live only in `config.py`
(`BASE_URL`, `SEARCH_BASE_URL`, `READER_BASE_URL`) — handlers
must not hardcode them.

## Usage history

All verbs must write `usage_history` with:

- `provider` = `jina-ai`
- `connection_id` = connection UUID (required for quota filter)
- `prompt_tokens` from upstream usage / `x-usage-tokens`

`/v1/search` and `/v1/web/fetch` pass `connection_id` like
embed/rerank. Rows with null `connection_id` are invisible to the
Quota Tracker for that connection.

## Rate-limits table

Catalog `RATE_LIMITS` → Provider Detail `RateLimitsNote`.

| Row | rpm | tpm | tokens |
|-----|-----|-----|--------|
| free | 500 | 1M | 10M (operator) |
| premium | 2k | 5M | — |
| search free | 100 | — | — |
| search premium | 1k | — | — |
| reader free | 500 | — | — |
| reader premium | 5k | — | — |

Embed/rerank RPM/TPM from docs. Search/reader RPM from docs.
Tokens grant operator-only.

## Quota tracker

`USES_UPSTREAM = False` (no usage API; skip stale cache on
read — list still refreshes local handlers).

Card bars (from `quota.py`):

| Bar | Window | Cap source |
|-----|--------|------------|
| free tokens | lifetime sum on this connection | `RATE_LIMITS.free.tokens` (free plan only) |
| RPM | last **60 seconds** request count | plan free/premium embed+rerank rpm |
| TPM | last **60 seconds** token sum | plan free/premium embed+rerank tpm |

Notes:

- Free-token grant is shared across embed/rerank/search/reader.
- Card RPM/TPM use **embed+rerank** caps only. Search/reader RPM
  appear in the RateLimitsNote table, not as separate card bars.
- After idle >60s, RPM/TPM used = 0 is expected.
- UI `accountType` free|payg|subscribe|premium → docs free|premium.
- Remaining % in the tracker UI is floored for display (99.7% →
  99% left); backend keeps the exact float.
