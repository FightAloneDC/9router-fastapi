# Grok CLI (Grok Build) Provider Flow

Written from `backend/app/providers/grok_cli/` only (catalog +
limits slice 2026-08-18). Do not copy another provider's FLOW.

Distinct from `xai` (api.x.ai API key) and `grok-web` (cookie).
This provider is OAuth device-code on `auth.x.ai` + inference on
`cli-chat-proxy.grok.com` (OpenAI **Responses** API, not Chat
Completions). Alias `gcli`. Catalog lives in `provider_models`.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, `RATE_LIMITS`, notice |
| `constants.py` | Hosts, OAuth URLs, fingerprint, model drop list |
| `oauth.py` | Device-code OAuth handler |
| `handler.py` | `/responses` URL, headers, validate, body build |
| `transform.py` | Chat → Responses body shaping |
| `models.py` | `GET /models` with CLI fingerprint |
| `quota.py` | Local daily tokens + header snapshot + health |
| `stream.py` | SSE / Responses stream helpers |
| `quality_gate.py` | Optional 407 / phantom-write gates (flags) |
| `bulk.py` | Farm JSON bulk import |
| `anomaly.py` / `debug_dump.py` | Diagnostics |
| `__init__.py` | Package marker |

## Constants (`config.py`)

```
PROVIDER_NAME        = Grok CLI (Grok Build)
PROVIDER_ID          = grok-cli
ALIAS                = gcli
BASE_URL             = https://cli-chat-proxy.grok.com/v1
FORMAT               = openai-responses
MODEL_CATALOG_TABLE  = True
SUPPORTS_BULK_IMPORT = True
SYNC_DISABLED_WITH_MODEL_LIST = True
```

Chat URL: `POST {BASE_URL}/responses`.

## Rate limits (Provider Detail table)

`RATE_LIMITS` → catalog `rateLimits` → `RateLimitsNote`.

Free daily token cap is **random per account** (operator):

| Key | tpd | requests |
|-----|-----|----------|
| `free/1m` | 1_000_000 | 21 |
| `free/500k` | 500_000 | 21 |

`requests` matches observed `X-Ratelimit-Limit-Requests`.
Do not invent RPM/TPM rows. Live used for tokens comes from
`usage_history` (UTC day); header **remaining** is often static
and ignored. When a free-usage 429 body includes
`tokens (actual/limit): A/B`, `B` calibrates that connection
(often 500000 while headers still say 1M).

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="gcli/<id>"
  → alias gcli → provider grok-cli
  → Bearer accessToken + CLI fingerprint headers
  → transform → Responses body
  → POST {BASE_URL}/responses
  → observe_upstream_response → GrokCliUsageHandler
  → stream/JSON back to client
  → usage_history tokens
```

## Models

`MODEL_CATALOG_TABLE` is True. Fetch writes `provider_models`.
`models.fetch_models` GETs `/models` with the same fingerprint.
Drop id `grok-build` (product name, not an API model). Default
API model constant: `grok-4.6` (see `constants.py`).

## Quota (`quota.py`)

`USES_UPSTREAM = False` (no trusted free-tier balance API).

1. **Used** — sum today's UTC prompt+completion from
   `usage_history`.
2. **Limit** — prefer today's `quota_cache` snapshot of
   `X-Ratelimit-Limit-Tokens`, else default
   `RATE_LIMITS["free/1m"]["tpd"]`; override from 429 body when
   present (`free/500k` path).
3. **Requests row** — from header Limit/Remaining-Requests when
   observed.
4. **Health** — `classify_health` on connection blob
   (429 / spending / dead).

## Auth

Device code: `auth.x.ai` (`GROK_CLI_CLIENT_ID`, referrer
`grok-build`). Refresh via token endpoint; lead time in
`constants.GROK_CLI_REFRESH_LEAD_SECONDS`.

## Related

- Catalog policy:
  `docs/architecture/2026-08-15-openrouter-catalog-slice.md`
- Quality gate design (separate):
  `docs/architecture/2026-08-15-grok-cli-quality-gate-design.md`
