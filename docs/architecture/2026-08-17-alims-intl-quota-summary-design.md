# Alibaba Studio quota tracker — summary + on-demand detail

Date: 2026-08-17  
Status: approved  
Provider: `alims-intl`

## Problem

`AlimsIntlUsageHandler.fetch()` seeded ~226 models × RPM/TPM into
`quota_cache` and `GET /quota`, producing ~1 MB XHR payloads.

## Decision

Grok-style card: **one small summary**, plus a **Model details**
button that loads the full per-model table only for the clicked
connection.

## Behavior

### Default (`fetch` / list / refresh)

Return **at most two** quota bars from local `usage_history`
(last 60 seconds), aggregated across models on that connection:

- `requests (last 60s)` — `used` = sum of requests; `unlimited`
- `tokens (last 60s)` — `used` = sum of tokens; `unlimited`

Do **not** emit the full `RATE_LIMITS` catalog. Persist only this
summary in `quota_cache`.

### Detail (`GET /usage/{id}?detail=models`)

Return per-model RPM/TPM rows (published caps + local usage /
optional header overlay). **Do not** write this payload into
`quota_cache`.

UI: button on Alibaba Studio cards only → modal (search + scroll).

### `observe_response`

Must not merge live headers onto a full published catalog. Keep
cache small (summary and/or last-model live rows only).

## Out of scope

Other providers; changing `RATE_LIMITS` content; filtering by
enabled models.
