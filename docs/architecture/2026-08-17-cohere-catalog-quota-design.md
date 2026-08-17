# Cohere catalog + quota tracker

Date: 2026-08-17  
Status: approved  
Provider: `cohere`

## Problem

Cohere still uses the legacy blob catalog (`data.models`) and has no
provider `quota.py` / `FLOW.md`. Chat rate limits in Cohere docs are
**per model**; non-chat paths are **per endpoint**; trial-tier keys
also have a **global 1,000 API calls / month** cap. Dumping every
model into `quota_cache` would repeat the Alibaba Studio payload
problem.

## Goal

Same optimization slice as OpenRouter / Groq / NVIDIA / Cerebras /
Mistral / `alims-intl`:

1. `MODEL_CATALOG_TABLE = True` → catalog in `provider_models`
2. Provider-specific quota in `providers/cohere/quota.py`
3. `FLOW.md` written from this provider’s code only
4. No new columns on `provider_connections`; secrets/health stay in
   `data`

## Catalog

- Set `MODEL_CATALOG_TABLE = True` on `CohereConfig`.
- Fetch / clear / enable write `provider_models` only.
- Do not write the model list back into connection `data.models`.
- Update `docs/architecture/2026-08-15-openrouter-catalog-slice.md`
  “On as of …” list to include `cohere`.

Existing chat path stays OpenAI-compat
(`https://api.cohere.com/compatibility/v1`). Existing native rerank
handler stays. No chat wire redesign in this slice.

## Account type (`data.accountType`)

Project convention only: `free` | `payg` | `subscribe`.
Default when missing: `free`.

Map to Cohere docs (trial vs production keys):

| `accountType` | Cohere meaning | Chat RPM (standard Command*) | Calls / month |
|---------------|----------------|------------------------------|---------------|
| `free` | Evaluation / trial key | 20 | **1000** |
| `payg` | Production pay-as-you-go | 500 | unlimited |
| `subscribe` | Same caps as `payg` in tracker | 500 | unlimited |

Newer Chat variants (Command A Reasoning / Translate / Vision / A+)
stay at trial-like RPM (20) even on paid keys per Cohere docs;
production self-serve RPM for those is “contact sales”. Tracker
publishes 20 RPM for those model ids on all account types unless
docs later publish a self-serve number.

## Rate limits (`RATE_LIMITS` in `config.py`)

Source: https://docs.cohere.com/docs/rate-limits

Structure follows other providers: plan prefix or plan keys plus
per-model / per-endpoint entries as needed for lookup. Exact dict
shape is an implementation detail; meaning must match:

**Chat (per model)** — trial/`free` 20 RPM; `payg`/`subscribe` 500
RPM for Command A, Command R+, Command R, Command R7B, North Mini
Code. Command A+ / Reasoning / Translate / Vision: 20 RPM (all
plans in this tracker).

**Other endpoints (not per model)**

| Endpoint | `free` | `payg` / `subscribe` |
|----------|--------|----------------------|
| Rerank | 10 RPM | 1000 RPM |
| Embed | 2000 inputs/min | 2000 inputs/min |
| Default | 500 RPM | 500 RPM |

Audio / EmbedJob / Tokenize / Embed(Images) may be listed in
`RATE_LIMITS` for completeness if cheap; detail UI may show only
models present in catalog + rerank/embed rows we actually proxy.

**Monthly (global)** — `free` only: 1000 API calls / calendar month
(UTC), all endpoints combined. `payg` / `subscribe`: no monthly bar.

## Quota tracker (Alibaba Studio pattern)

`USES_UPSTREAM = False`. Local `usage_history` + published
`RATE_LIMITS`. Optional header overlay only when Cohere sends
rate-limit headers.

### Default `fetch` / list / refresh

Persist a **small** summary in `quota_cache`:

1. `requests (last 60s)` — used from local logs; `unlimited`
2. `tokens (last 60s)` — used from local logs; `unlimited`
3. If `accountType` is `free` (or missing → free):
   `calls (month)` — used since UTC month start vs **1000**

Do **not** seed the full per-model table into `quota_cache`.

### Detail `fetch_model_details`

Triggered by `GET /usage/{id}?detail=models`. Return per-model Chat
RPM rows (+ endpoint Rerank/Embed rows as above) with local usage /
optional header overlay. **Do not** write this payload into
`quota_cache`.

### `observe_response`

Must not merge live headers onto a full published catalog. Keep
cache to summary and/or last-model live rows only.

### UI

Quota Tracker ListTree / Model details button: enable for `cohere`
the same way as `alims-intl` (gate on provider id for this slice;
no Quota Tracker redesign).

## Files

| File | Change |
|------|--------|
| `backend/app/providers/cohere/config.py` | Catalog flag, `RATE_LIMITS`, notice text |
| `backend/app/providers/cohere/quota.py` | **Create** — summary + `fetch_model_details` |
| `backend/app/providers/cohere/FLOW.md` | **Create** — from this folder’s code |
| `backend/app/providers/cohere/handler.py` | Touch only if observe/validate needs it |
| `backend/app/providers/cohere/models.py` | Unchanged unless fetch path needs it |
| `frontend/src/pages/QuotaTrackerPage.jsx` | Show model-details for `cohere` |
| Catalog slice doc | Add `cohere` to enabled list |

Register `CohereUsageHandler` the same way other API-key providers
register (existing quota registry pattern). No shared
“per-model-limit providers” list in routers beyond the existing
`detail=models` dispatch via `fetch_model_details`.

## Success

- Fetch/clear/disable use `provider_models` for `cohere`.
- Quota list payloads stay small; detail loads only on demand.
- `free` shows monthly 1000; `payg` / `subscribe` do not.
- Detail shows per-model Chat RPM from config + local usage.
- `FLOW.md` exists and matches implemented behavior.
- No credential columns added; no blob catalog writes on fetch.

## Out of scope

- Other providers
- Redesigning chat/rerank wire formats
- Cohere billing/usage HTTP API as primary source
- Filtering detail rows by enabled catalog models (same as alims)
- Changing OpenRouter/Groq/`alims-intl` handlers
- Auto-detecting trial vs production from the API key string
  (user sets `accountType` in connection data / UI)
