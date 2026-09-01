# Qoder Provider Flow

Written from `backend/app/providers/qoder/` only (catalog slice
2026-08-18). Do not copy another provider's FLOW.

Qoder is **not** OpenAI-compatible. Chat uses a COSY-signed
`/algo` endpoint, WAF-bypass body encoding, and a custom response
envelope. Auth is device OAuth and/or PAT → job token exchange.
Alias `qd`. Connection `data` holds secrets/health only
(`accessToken`, `refreshToken`, `userId`, `machineId`, …) — not
the model list.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, `MODEL_CATALOG_TABLE`, PAT/bulk flags |
| `constants.py` | Hosts, chat/model URLs, COSY IDE constants, RSA key |
| `cosy.py` | RSA+AES+MD5 COSY headers (`Bearer COSY.…`) |
| `encoding.py` | WAF-bypass body alphabet encode |
| `models.py` | Live `/algo/api/v2/model/list` + in-memory `raw_configs` |
| `transform.py` | OpenAI → Qoder body; unwrap envelope / SSE |
| `handler.py` | Validate, URL/headers/body, unwrap, fetch_models |
| `auth.py` | Device flow, PAT import, jobToken refresh |
| `oauth.py` | `QoderOAuthHandler` (device + refresh map) |
| `quota.py` | `QoderUsageHandler` → openapi quota/usage |
| `bulk.py` | Farm JSON bulk import |
| `__init__.py` | Public exports |

⚠️ Do not change `cosy.py` / auth without evidence. Investigation
log: `docs/archives/qoder-docs/BUG-FIXING-LOG.md`.

## Constants (`config.py` / `constants.py`)

```
PROVIDER_NAME        = Qoder
PROVIDER_ID          = qoder
ALIAS                = qd
BASE_URL             = https://api3.qoder.sh
FORMAT               = qoder
VALIDATION_TYPE      = qoder
MODEL_CATALOG_TABLE  = True
SUPPORTS_PAT         = True
SUPPORTS_BULK_IMPORT = True
RATE_LIMITS          = trial → credits 300, days 14

openapi              = https://openapi.qoder.sh
center               = https://center.qoder.sh
chat (algo)          = https://api3.qoder.sh/algo/...
CHAT_URL_ENCODED     = .../agent_chat_generation?...&Encode=1
MODEL_LIST_URL       = .../algo/api/v2/model/list
QODER_IDE_VERSION    = 1.0.48  (Cosy-Version / User-Agent)
                     catalog omits keys whose
                     minimal_version.cli is newer
                     (cmodel/Cantus needs 1.0.48)
QUOTA_USAGE_URL      = .../api/v2/quota/usage
REFRESH              = .../api/v1/jobToken/refresh
```

## Catalog vs chat `model_config`

Two layers — do not conflate them.

| Concern | Store | Source |
|---------|-------|--------|
| UI / `/v1/models` list | SQL `provider_models` | `MODEL_CATALOG_TABLE` |
| Full upstream entry for chat | Process RAM `_catalog_cache` | `models.py` `raw_configs` |

`handler.fetch_models` calls `resolve_qoder_models` (COSY GET
model list) and stores the upstream `key` as the catalog id
(`auto`, `qmodel`, …). Public `/v1/models` id is `qd/<key>`.
Do not prefix `qoder/` onto the catalog id (that produced the
broken `qd/qoder/<key>`). With the catalog flag on,
fetch/set/clear persist **id/name/type** into
`provider_models` — never `data.models`.

Chat `build_request_body` needs the **entire** upstream list entry
as `model_config` (wrong/incomplete config → silent upstream
downgrade). That comes from `get_qoder_model_config` →
`_catalog_cache[…].raw_configs`, TTL 1 hour, keyed by user +
token. Miss → force-refresh model list. **Not** stored in SQL.

## Auth

1. **Device flow** — PKCE + nonce; poll
   `openapi…/deviceToken/poll`; token `dt-…`.
2. **PAT** — `pt-…` → `POST …/jobToken/exchange` → job token +
   refresh; then `userinfo` for `userId` / email / name;
   generate `machineId`. Keep `personalToken` (`pt-…`) in
   connection `data` (bulk farm `tokens.personal_token` and
   UI PAT import). Job tokens expire; the PAT is the
   re-exchange key. Export dumps `data` as-is, so the PAT
   survives a later import.
3. **Validate** — `fetch_user_info` (token present but inactive
   still fails chat later).
4. **Refresh** — `POST …/jobToken/refresh`:
   - on-demand: `try_refresh_on_auth_error` after 401/403
   - background: `refresh_all_qoder_connections` every ~5 min
     via `token_refresh.py` — POST only when `expiresAt` is
     within 1h (or missing). Not every active account.
   - if refresh is dead/missing, re-exchange stored
     `personalToken`; only then mark the refresh unusable

`data` must keep `userId` + `machineId` for COSY.

## Entry: proxy chat

```
Client POST /v1/chat/completions  model="qd/auto"
  → alias qd → provider qoder, remainder "auto"
  → build_upstream_url → QODER_CHAT_URL_ENCODED (Encode=1)
  → build_headers / build_request_body:
       qoder_key is the remainder ("auto"); leftover
       "qoder/auto" is not a valid key

       get_qoder_model_config (RAM) or refresh list
       transform OpenAI body → Qoder JSON + model_config
       qoder_encode_body (WAF alphabet)
       build_cosy_headers(body=encoded) → Bearer COSY.…
  → POST algo chat
  → unwrap_response / SSE unwrap → OpenAI shape
  → usage_history as usual (tokens.credits from SSE usage)
  → observe_after_request → QoderUsageHandler.observe_complete
       sum tokens.credits → quota_cache
```

`observe_response` is a no-op (no credit remaining headers;
headers also arrive before the stream finishes). Chat SSE
`usage` includes ``credits`` / ``original_credits`` (verified
2026-09-01). That JSON is stored on `usage_history.tokens`.
`fetch()` takes max(live API used, full-float sum of those
credits). Never `int()` or round credits. `observe_complete`
writes that local sum into `quota_cache` right after the
history row — same lifecycle as NVIDIA.

SSE unwrap lives in `transform.unwrap_qoder_sse_line` (also
called from `v1_proxy/shared` for the streaming path). Business
envelopes (e.g. code `112` pricing, `TOKEN_EXPIRE`) map to HTTP
status via `qoder_envelope_http_error`. Chat peek raises 402 so
the pool can rotate; `mark_connection_unavailable` classifies
402 / pricing / quota as **exhausted** and sets
`is_active=False` (plus 1h cooldown metadata via `ERROR_RULES`).
Re-enable via Provider Detail or `POST /quota/bulk-enable-inactive`.

## Rate limits (Provider Detail table)

`QoderConfig.RATE_LIMITS` is served as catalog `rateLimits` →
`RateLimitsNote` on `/providers/qoder`. Published row only:

| Key | credits | days |
|-----|---------|------|
| `trial` | 300 | 14 |

Per account/connection. No RPM/TPM — do not invent. Source:
operator 2026-08-18 + quota API (`userQuota.total` ≈ 300,
`expiresAt` ≈ 14-day window). `QoderMetadata.notice.text`
summarizes the same.

## Quota (`quota.py`)

`QoderUsageHandler` GETs `QODER_QUOTA_USAGE_URL` with Bearer
access token (not COSY). Reads live `userQuota` credits +
`isQuotaExceeded` / `expiresAt`. If upstream `total` is missing,
falls back to `RATE_LIMITS["trial"]["credits"]`. Live remaining
always wins over a grok-farm-modular last check.

`reset_at` is API `expiresAt` (trial/account end), else blob
`proTrialEndAt`. Do not use `tokens.expires_at` / blob
`expiresAt` — that is job-token TTL. If the GET fails, the
handler may show the farm snapshot (`farmQuota*` +
`proTrialEndAt`) instead of an empty error.

`USES_UPSTREAM = True` — tracker `GET /quota` serves
`quota_cache` (no live poll per tick). `fetch()` still GETs
the live quota API on `GET /usage/{id}` (15 min cache, or
`force=true`).

After each proxied chat, `observe_complete` (from
`save_request_tracking`) sums `usage_history.tokens.credits`
into `quota_cache` so the next list tick is not the first
refresh. `fetch()` takes max(API used, local credit sum) as
full floats — never `int()` / `round()` in Python, cache, or
JSON. Tracker UI may show 2 decimal places (display only).

Snapshot may land in `quota_cache` via the shared quota
router — not the model blob.

## Models fetch (operator)

1. Provider Detail → Fetch Models (any active connection).
2. Rows appear in `provider_models` for `provider=qoder`.
3. Chat still needs a successful COSY model-list fill into RAM
   before the first request if cache is cold.

## Related

- Open problems (optional billing piggyback):
  `docs/architecture/2026-09-01-qoder-open-problems.md`
- Catalog policy:
  `docs/architecture/2026-08-15-openrouter-catalog-slice.md`
- Token / cache bugs (historical):
  `docs/archives/qoder-docs/`
- Handbook OAuth / Qoder expiry notes:
  `docs/architecture/handbook.md`
