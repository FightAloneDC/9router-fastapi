# Command Code Provider Flow

Written from `backend/app/providers/commandcode/` only.

`CommandcodeConfig.BASE_URL` is `https://api.commandcode.ai/provider/v1`.
Auth is Bearer `data.apiKey` on all endpoints. One API key serves
both OpenAI-shaped and Anthropic-shaped upstream paths depending on
model id.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, catalog flag, credit `RATE_LIMITS`, Studio plan options, notice |
| `handler.py` | Per-model format + URL; validate connectivity hint |
| `models.py` | `GET /models` list parsing |
| `quota.py` | Published credit caps (no upstream poll) |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_ID          = commandcode
ALIAS                = cmc
BASE_URL             = https://api.commandcode.ai/provider/v1
FORMAT               = openai (default; Claude ids override per model)
MODEL_CATALOG_TABLE  = True
CATEGORY             = freeTier
CLAUDE_MODEL_PREFIX  = claude-
```

Credit windows in `RATE_LIMITS` (USD whole dollars, keys
`monthly`, `window_5h`, `weekly`). Studio subscription tiers (all
monthly subscribe plans on commandcode.ai): `go`, `goat`, `pro`,
`max_10x`, `max_20x`, `team_pro`, `provider` (PAYG — no rolling
windows in docs).

`STUDIO_PLAN_OPTIONS` → catalog `studioPlanOptions` → connection row
dropdown. Stored on connection as `data.studioPlan`.

`accountType` (`free` / `payg` / `subscribe`) is **9Router farm
metadata only** — never mapped to Studio tiers.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="cmc/claude-sonnet-5"
  → alias cmc → provider commandcode
  → CommandcodeHandler.resolve_upstream_format → "claude"
  → openai_to_claude_request(body)
  → POST {BASE_URL}/messages  (Bearer)
  ← Anthropic SSE → OpenAI JSON/SSE to client

Client POST /v1/chat/completions  model="cmc/gpt-5.6-sol-medium"
  → resolve_upstream_format → "openai"
  → POST {BASE_URL}/chat/completions  (Bearer)
  ← OpenAI-shaped response
```

Wrong path (Claude model on `/chat/completions`) returns 400 from
upstream — handler prevents that.

## Models

`GET {BASE_URL}/models` → `{data: [{id, ...}]}`. Writes
`provider_models` when fetch runs (`MODEL_CATALOG_TABLE`).

**Go plan — no Provider API (operator: 2026-08-29):** `studioPlan=go`
→ chat and messages return 403 `upgrade_required`. Studio UI credits
still exist in docs (`RATE_LIMITS["go"]`) but 9Router cannot proxy
API traffic on Go. `validate()` fails early when `studioPlan` is
`go`; `PLANS_WITHOUT_PROVIDER_API` in `config.py`.

**Validate limitation:** `/models` returns 200 without auth and with
invalid Bearer — connectivity probe cannot detect bad keys on
GOAT+; live chat is the real check.

## Quota

No published usage API. ``CommandcodeUsageHandler`` shows doc
caps vs local ``usage_history.cost`` estimate per rolling window
(month UTC start, 5h, 7d). Not Command Code's official meter —
compare Studio. Connection **`studioPlan`** selects the tier.

## Rate limits

Official docs use rolling credit windows, not RPM/TPM. Catalog
`rateLimits` table shows `monthly` / `window_5h` / `weekly` per plan.
429 = upstream rate limit; retry with backoff (no documented
`x-ratelimit-*` headers).

## Sources

| URL | Retrieved |
|-----|-----------|
| https://commandcode.ai/docs/provider | 2026-08-28 |
| https://commandcode.ai/docs/resources/usage-limits | 2026-08-28 |
| https://commandcode.ai/docs/resources/pricing-limits | 2026-08-28 |
| Live `GET /provider/v1/models` (no auth / invalid key → 200) | 2026-08-29 |
