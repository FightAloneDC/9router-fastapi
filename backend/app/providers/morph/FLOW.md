# Morph Provider Flow

Written from `backend/app/providers/morph/` and official Morph docs
(retrieved 2026-08-18). Case-closed notes (Pi agent fit) updated
2026-08-18 from live A/B + operator tests.

`MorphConfig.BASE_URL` is `https://api.morphllm.com/v1` — it already
ends in `/v1`, so URL building must never append a second copy
(chat: `POST /v1/chat/completions`). Auth is one Bearer key
(`Authorization: Bearer ***`) for every product, created at
`https://www.morphllm.com/dashboard/api-keys`. Catalog lives in
`provider_models` (SQL). The only published numeric cap is the free
tier's **200 requests per month**; `quota.py` tracks that as a
local monthly bar (no upstream usage API, no rate-limit headers).

## Product classes (suitability)

One Morph key covers several product lines. They are **not**
interchangeable.

| Class | Example ids | Role | Pi / agent? |
|-------|-------------|------|-------------|
| **Apply** | `morph-v3-fast`, `morph-v3-large`, `auto` | Code merge | **No** |
| **Fast Models** | `morph-kimik3`, `morph-qwen*`, `deepseek/deepseek-v4-flash-0731` | Chat + OpenAI `tools` | **Yes** |
| **Warp Grep** | `morph-warp-grep-*` | Built-in grep tools | Grep only |

### Apply (`morph-v3-fast` / `morph-v3-large` / `auto`)

Official marketing (OpenRouter / Morph models pages, 2026-08-18):
both are **apply** models for code edits. Same required prompt:

```
<instruction>{instruction}</instruction>
<code>{initial_code}</code>
<update>{edit_snippet}</update>
```

Output is the **merged file** in `message.content`. They are not
chat LLMs and not tool agents. Fast ≈ higher throughput / ~96%
apply accuracy; Large ≈ higher accuracy / ~98%. Do **not** use
Apply ids as the Pi planner (AGENTS.md + bash + write_file).

Live 2026-08-18 (identical chat prompt, Morph API):
- `morph-v3-fast` no tools → exact echo of the user prompt
- `morph-v3-large` no tools → invents Python/`subprocess` code
- `tools` + `tool_choice=none`: fast → large garbage dump;
  large → XML `<tool_call>` in content (not native OpenAI tools)

**Case closed:** stop adapting Apply into a Pi agent. Use Fast
Models for agents; use Apply only for merge clients that already
send the XML above.

### Fast Models (agent / chat)

Keep client `tools` / `tool_choice` (real OpenAI `tool_calls`).
Kimi K3 omits null `content` when a message carries tools.

Pi **write file** verified 2026-08-18 (operator):

- `mo/morph-kimik3`
- `mo/deepseek/deepseek-v4-flash-0731`

## Sources

| # | URL | What it is | Retrieved |
|---|-----|-----------|-----------|
| S1 | https://docs.morphllm.com/llms.txt | Documentation index (products, auth, Fast Models table) | 2026-08-18 |
| S2 | https://docs.morphllm.com/api-reference/endpoint/models | `GET /v1/models` (ids only), auth, 429 body | 2026-08-18 |
| S3 | https://docs.morphllm.com/api-reference/endpoint/apply | `POST /v1/chat/completions`, usage fields | 2026-08-18 |
| S4 | https://docs.morphllm.com/api-reference/endpoint/report | `POST /api/report` (quality feedback); documents `x-completion-id` | 2026-08-18 |
| S5 | https://www.morphllm.com/api/models/json | Public machine-readable live model list (schema_version 2.4) | 2026-08-18 |
| S6 | https://www.morphllm.com/models | Marketing model table with exact ids, pricing, context | 2026-08-18 |
| S7 | https://www.morphllm.com/pricing | "No limits — practically no rate limits"; 200 req/mo free | 2026-08-18 |
| S8 | https://www.morphllm.com | Home: "High Rate Limits", "99.9% uptime SLA" | 2026-08-18 |
| S9 | https://docs.morphllm.com/sitemap.xml | Full docs sitemap: NO rate-limits page, NO usage API page | 2026-08-18 |
| S10 | https://docs.morphllm.com/guides/xml-tool-calls.md | Client-harness XML tool calls (Cursor/Cline); not Apply `tools` | 2026-08-18 |

`https://docs.morphllm.com/rate-limits` → 404 (no such page).

S10 is a **client** guide (WIP): planner LLMs may emit XML
(`<edit_file>…</edit_file>`) then map into Apply merge XML (S3)
or Fast Models JSON `tools` (S1). Separately, live Apply with
`tools` + `tool_choice=none` returns tool intents as
`<tool_call>…</tool_call>` in content — this proxy converts that
to OpenAI `tool_calls` (it does not invent Cursor/Cline agent
mapping from S10).

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, UI metadata. `RATE_LIMITS` keys are the three account tiers: `free` / `payg` / `subscribe` |
| `models.py` | `fetch_models` via `fetch_models_header_auth` |
| `quota.py` | Local monthly free-request bar from `usage_history` |
| `handler.py` | `prepare_request` → sanitize; `unwrap_response` + SSE convert Apply `<tool_call>` → OpenAI `tool_calls`; no farm rotate on charCodeAt |
| `transform.py` | Apply tools path (`tool_choice=none`); merge XML wrap when no tools; XML tool_call parse; Warp strip client tools; Fast Models passthrough tools |
| `__init__.py` | Package marker |

## Rate limits — only the free monthly cap is published

Official `/pricing` (S7, retrieved 2026-08-18) maps onto the
three connection `accountType` rows used in the UI:

| `accountType` | Morph billing name | Published request cap |
|---|---|---|
| `free` | Free / 200 req/mo | `calls=200` (per calendar month) |
| `payg` | Pay as you go (credits from $10) | none — "practically no rate limits" |
| `subscribe` | Scale ($200/mo, 40M credits) | none — "practically no rate limits" |

Dedicated / reserved endpoints are out of scope (not in this
table).

There is still **no** official RPM / RPD / TPM / TPD table (S9;
`/rate-limits` 404s). `calls` is monthly requests, not RPD.
`RATE_LIMITS` therefore is:

```
free        calls=200
payg        {}
subscribe   {}
```

Adding RPM/TPD/TPM numbers would be inventing values.
The Provider Detail table shows a `calls` column when any row
has that key (generic — not a Morph-only UI branch).

### 429 behavior

429s do occur and the error envelope is OpenAI-style
`{"error":{"code":...,"message":...}}` with codes
`invalid_request_error` / `unauthorized` / `rate_limited` /
`internal_error` (S2/S3). The documented 429 body embeds the retry
delay in the **message text** ("Too many requests. Retry in 12
seconds.") — not in a header. No `x-ratelimit-*` header is
documented for any endpoint; the only documented response header is
`x-completion-id` (report endpoint, S4). Success responses carry no
remaining counts.

One exception: GLM-5.2 with `service_tier: "standby"` can return
429 with `error.code: "resource_unavailable"` and a `Retry-After`
header (S1 standby note) — nothing generated, nothing billed.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="mo/<id>"
  → alias mo → provider morph
  → MorphHandler.prepare_request → sanitize_morph_chat_body
       flatten list/dict content → string (JS charCodeAt contract)
       drop Pi `store`
       Apply (morph-v3-fast|large|auto) — merge only, not agents:
         Official input is always one user message with
         <instruction>/<code>/<update> (S3 + marketing pages).
         Allowlist model/messages/stream/max_tokens/temperature;
         map max_completion_tokens → max_tokens; default
         temperature 0 if omitted.
         morph-v3-fast (proxy path, live 2026-08-18):
           Pi system/developer becomes the "merged file" if
           forwarded. Non-XML chat: wrap last user only into
           Apply XML with one space in <code>/<update>; strip
           tools; drop system. Real last-user Apply XML
           passthrough. Response rewrites (echo drop / optional
           shell→tool_calls) are legacy mitigations — do not
           treat fast as an agent product.
         morph-v3-large / auto:
           A) Client tools[]: keep turns; tools; tool_choice=none
              (auto/omit/required → HTTP 400 without Morph's
              tool-call-parser; tools+none → XML <tool_call> in
              content). Workaround only — still not a Fast Model.
           B) No tools: collapse to Apply XML. Client already has
              <code>+<update>: one user. Chat without XML: wrap
              (system+history+user in <instruction>; chat marker
              in <update>). User text in <update> echoes.
       Warp Grep (morph-warp-grep-*): drop client tools array only;
         keep assistant tool_calls + tool results (multi-turn)
       Fast Models: keep tools for auto/omit/required/none
         (live: OpenAI tool_calls). Do NOT strip on auto.
         Preferred for Pi agents (kimik3 / dsv4flash verified).
       Kimi K3: omit content when message carries tools (S1)
  → Bearer data.apiKey
  → POST {BASE_URL}/chat/completions
  → MorphHandler.unwrap_response / SSE_LINE_TRANSFORM
       Apply **output**:
         - <tool_call>…</tool_call> in content → OpenAI tool_calls
           (finish_reason=tool_calls); SSE buffers across deltas
         - other XML (<reply>, Apply envelope, <code>) → unwrap text
         - plain merged file text passes through
  → OpenAI-shaped response with usage
  → usage_history
```

Official product rules for tools (S1 + live A/B 2026-08-18):

- **Fast Models** — support `tools`, `response_format`, structured
  outputs; return OpenAI `tool_calls`. Use these for Pi / agents
  (`morph-kimik3`, `deepseek/deepseek-v4-flash-0731`, …).
- **Kimi K3** (`morph-kimik3`, `morph-kimik3-fast`) — dynamic tool
  loading via a `system` message with `tools` and **no** `content`
  key (`content: null` → HTTP 400). `tool_choice` may be `required`.
- **Apply** — merge XML only (S3 + OpenRouter Morph pages). Same
  format for fast and large. Live may accept `tools` with
  `tool_choice="none"` and emit XML `<tool_call>` in content; the
  proxy can convert that to OpenAI `tool_calls`, but Apply is still
  **not** an agent product. Catalog `tools:true` is incomplete —
  do not treat catalog alone as the contract.
- **Warp Grep** — built-in tools; do **not** pass a client `tools`
  array; multi-turn still uses `tool_calls` / `tool` messages.

OpenAI `usage` fields are returned in every chat response (S3), so
local per-request usage tracking works. No upstream remaining exists
to overlay.

## Quota (`quota.py`)

`MorphUsageHandler` — `PROVIDER_ID = "morph"`,
`USES_UPSTREAM = False` (the router does not poll a Morph usage
API; none is documented, S9). Registered automatically by the
quota registry (`app/services/quota/__init__.py`).

### List / refresh (`fetch`)

One bar, free tier only (`accountType` `free` is the default):

- `Morph monthly free requests` — this connection's
  `usage_history` rows since UTC month start vs **200**
  (`RATE_LIMITS.free.calls`), reset at the next UTC month
  start. `limit_reached` when used ≥ 200.

Paid/payg `accountType` → empty quotas (no published cap) with a
message explaining that only the free tier has a cap.

Results always reflect current local usage — nothing is written to
`quota_cache` (there is no upstream remaining to cache).

### `observe_response`

Not overridden: Morph documents no `x-ratelimit-*` headers
(S2/S3/S4), so there is nothing to observe.

## Catalog

`MODEL_CATALOG_TABLE` is True. Model rows live in `provider_models`
— the catalog is SQL, per the project policy
(`docs/architecture/2026-08-15-openrouter-catalog-slice.md`).
Fetch must **not** write the catalog into connection `data.models`
(project invariant).

`models.fetch_models(api_key)` GETs `{BASE_URL}/models` (i.e.
`https://api.morphllm.com/v1/models`, authenticated, S2) with Bearer
header auth and returns the OpenAI `data` list. `GET /v1/models`
returns the ids **your key** can call; the public catalog
`https://www.morphllm.com/api/models/json` (S5) is the cost/context
source ("regenerated from the same source as billing").

### Unresolved id discrepancies (flagged, not silently resolved)

- `morph-dsv4flash` vs `morph-dsv4flash-0731` — both present in S5
  (same weights, different openrouter slug; looks like a
  duplicate/alias).
- `morph-compact` (S7 pricing) vs `morph-compactor` (S6/S3) — same
  product, two ids.
- Specialized ids absent from S5: `morph-warp-grep-v2.1`,
  `morph-reflex-v1`, `morph-router`, `morph-compactor` (they appear
  on S6/S3 only).
- S1 Fast Models table lists `morph-minimax27-230b` which is absent
  from S5/S6 — stale table or decommissioned model.

These are left UNRESOLVED: ask the vendor or verify live before
cataloging them.

## Implementation notes (this vendor only)

- `BASE_URL` already ends in `/v1` — never append `/v1` again.
- One key works for every product (S1 auth, S2).
- Native endpoints that are NOT chat completions and are not wired
  in this slice: `POST /v1/compact`, `POST /v1/reflex/predict`,
  `POST /v1/router/classify`, `POST /v1/router/multimodel`,
  `POST /v1/responses`, Anthropic-format `POST /v1/messages` (S1).
- Kimi K3 dynamic tool loading (S1): handler keeps message-level
  `tools` and omits null `content`. Do not strip Fast Model tools.
- Apply ids are merge-only (case closed 2026-08-18): do not use
  `morph-v3-fast` / `morph-v3-large` / `auto` as Pi agents; prefer
  Fast Models (`morph-kimik3`, `deepseek/deepseek-v4-flash-0731`).
- No usage/credits/balance API exists publicly (S9) — dashboard
  credits polling is undocumented and not built.
- Native non-chat paths (`/v1/compact`, `/v1/reflex/predict`,
  Anthropic `/v1/messages`, …) stay unwired in this slice.
