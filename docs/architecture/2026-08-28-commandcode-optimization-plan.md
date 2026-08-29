# Command Code Provider Optimization Plan

Status: **approved — implementing** (2026-08-29)
Provider: `commandcode` (alias `cmc`)
Folder: `backend/app/providers/commandcode/`
Retrieved: 2026-08-28 (live probes updated 2026-08-29)

## 1. Current state (pre-implementation)

| File | Present | Notes |
|------|---------|-------|
| `config.py` | Yes | Minimal: identity only; wrong `BASE_URL` |
| `models.py` | Yes | Shared `fetch_models_header_auth` helper |
| `__init__.py` | Yes | Package marker |
| `handler.py` | No | Falls back to `BaseProviderHandler` |
| `quota.py` | No | No usage handler |
| `FLOW.md` | No | Unoptimized |

Config flags before fix: `MODEL_CATALOG_TABLE` unset, `CATEGORY`
empty, `RATE_LIMITS` absent, no plan notice text.

## 2. Verified findings

### F1. BASE_URL is wrong — provider is fully broken

`config.py` sets `BASE_URL = "https://api.commandcode.ai/v1"`.

Curl evidence (2026-08-28, reconfirmed 2026-08-29):

- `GET https://api.commandcode.ai/v1/models` → 404
- `GET https://api.commandcode.ai/provider/v1/models` → 200, 62 models

Correct base: `https://api.commandcode.ai/provider/v1`.

### F2. Two upstream endpoint formats, split by model family

Official docs (https://commandcode.ai/docs/provider, retrieved
2026-08-28):

| Endpoint | Format |
|----------|--------|
| `/provider/v1/chat/completions` | OpenAI Chat Completions |
| `/provider/v1/messages` | Anthropic Messages |
| `/provider/v1/models` | Models list |

Live catalog (2026-08-29): 62 models — 7 Claude (`claude-*`), 55
non-Claude. Wrong endpoint → 400 `invalid_request_error`.

**Resolution (decision A):** generic per-model format hook on
`BaseProviderHandler.resolve_upstream_format(model)` — default
returns `config.FORMAT`; `CommandcodeHandler` returns `"claude"`
when model id starts with `claude-` (after alias strip). Proxy
routers call the handler hook instead of reading `c.FORMAT` once.
`build_upstream_url` routes Claude ids to `/messages`. No
`if provider == "commandcode"` outside the provider folder.

### F3. Catalog debt

`MODEL_CATALOG_TABLE` unset → model list still in connection `data`
blob. Fix: enable flag; fetch writes `provider_models`.

`/provider/v1/models` returns `context_length` per model.
`BaseProviderHandler._normalize_model` drops it — deferred (not
required for wire fix).

### F4. Limits are credit windows, not RPM/TPM

Docs (https://commandcode.ai/docs/resources/usage-limits). Units are
USD credit value per rolling window:

| Plan | Cost | Monthly | 5-hour | Weekly |
|------|------|---------|--------|--------|
| Go | $1 | $10 | $3 | $6 |
| GOAT | $10 | $70 | $14 | $35 |
| Pro | $20 | $80 | $16 | $40 |
| Max 10x | $100 | $150 | $45 | $90 |
| Max 20x | $200 | $300 | $90 | $180 |
| Team Pro | $40 | $40 | $12 | $24 |

Extra pay-as-you-go credits uncapped. Provider plan ($15/mo) is
pay-as-you-go with no windows.

`RATE_LIMITS` keys: `go`, `goat`, `pro`, `max_10x`, `max_20x`,
`team_pro`, `provider`. Values: `monthly`, `window_5h`, `weekly`
(whole USD from docs). Go → `{}` (no API). Provider → `{}`.

### F5. No public usage/quota API

No balance or usage endpoint documented. `quota.py` shows published
credit caps from `RATE_LIMITS` (informational); `USES_UPSTREAM =
False`. Exact spend: Studio UI only.

### F6. Plan access restriction

Go plan ($1) → API 403 `upgrade_required`. Notice + validate hint
for users on Go.

### F7. Error envelope (OpenAI shape)

Types: `invalid_request_error`, `authentication_error`,
`permission_error`, `rate_limit_error`, `server_error`. Notable:
`upgrade_required` (403), `unsupported_model` (400),
`cmd_zdr_no_providers` (422).

### F8. Auth probe limitation (operator: 2026-08-29)

`GET /provider/v1/models` returns **200 with no auth** and **200
with invalid Bearer**. `validate()` via `/models` cannot detect bad
keys — document in FLOW.md; live chat is the real key check.

### F9. Optional zero-data-retention header

`x-cmd-zdr: 1` — out of scope unless requested.

## 3. Implementation checklist

| # | Item | Files |
|---|------|-------|
| 1 | Fix `BASE_URL` | `config.py` |
| 2 | Hybrid Claude routing | `config.py`, `handler.py`, `base.py`, `shared.py`, `chat.py`, `messages.py`, `routers/models.py` |
| 3 | `MODEL_CATALOG_TABLE = True` | `config.py` |
| 4 | `CATEGORY`, notice, `STUDIO_PLAN_OPTIONS` + `studioPlan` wiring | `config.py`, catalog, connections, UI |
| 5 | `RATE_LIMITS` credit windows | `config.py` |
| 6 | Informational `quota.py` | `quota.py` |
| 7 | `FLOW.md` | `commandcode/FLOW.md` |
| 8 | Tests | `tests/test_commandcode_provider.py`, `test_quota_handlers.py` |

## 4. Phases (execution order)

1. **Revise this plan** — done 2026-08-29.
2. **Wire + catalog + limits + FLOW** — full path in one change set
   (one provider per SOP).
3. **Verify** — pytest, `rg` for PS leaks, statics in `config.py`.

## 5. Decision A — resolved

Chosen: **generic per-model format hook** (was option 1 + 4 combined).

- `BaseProviderHandler.resolve_upstream_format(model) → str`
- `CommandcodeHandler`: `"claude"` if `claude-*`, else `"openai"`
- `CommandcodeHandler.build_upstream_url`: `/messages` vs
  `/chat/completions`
- Routers: `upstream_format_flags(provider, model)` in
  `v1_proxy/shared.py`

Rejected: exclude Claude from catalog (loses Opus/Sonnet). Split
provider ids (one key invariant).

## 6. Not in scope

- CLI/agent-farm (`scripts/agent_farm`)
- ZDR header (F9)
- `context_length` passthrough (deferred)
- BYOK providers feature

## 7. Sources

| URL | Retrieved | Used for |
|-----|-----------|----------|
| https://commandcode.ai/docs/provider | 2026-08-28 | Endpoints, errors, plans |
| https://commandcode.ai/docs/resources/pricing-limits | 2026-08-28 | Plans table |
| https://commandcode.ai/docs/resources/usage-limits | 2026-08-28 | Rolling windows |
| Live `GET /provider/v1/models` | 2026-08-29 | 62 models, no-auth 200 |
| Live invalid Bearer `/models` | 2026-08-29 | F8 — still 200 |
