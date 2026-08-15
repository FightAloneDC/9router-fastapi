# Grok CLI quality gate (literal 407)

Date: 2026-08-15

## Problem

Plenger grok-cli accounts still return HTTP 200. JWT scans, status
checks, and a soft ping do not catch them. They answer with the wrong
literal (observed: `202` when asked for `407`).

## Goal

Before a grok-cli connection is used for a user chat, require a
plain-chat probe. Pass = the model output is exactly `407`. Fail =
anything else. Skip the account and try the next candidate.

## Probe

- Model: `gcli/grok-4.6` (API id `grok-4.6`). Never `grok-build`.
- Body: one user message, no system, no tools, `stream: false`.

  `reply exactly with : 407`

- Target: that connection only. Short timeout (15–30s). No pool
  fallback on the probe.
- Pass: stripped content equals `407`.
- Fail: every other outcome (wrong text, tools, timeout, HTTP error).
  Do not special-case `202`.

## When

Before every grok-cli user chat, on the connection about to be used.

No TTL cache. Playground on one account returned `202`, `407`,
`202` within 53 seconds — a 2-hour cache would be wrong.

Cost: probe is one short user line (observed ~200 prompt tokens),
no system prompt. Agent turns carry hundreds or thousands of
system/tool characters. The probe is cheap next to the real request.

Fail → skip that connection, probe the next candidate. Same rule:
one connection per probe, no pool fallback on the probe itself.

## Storage

Optional last result on the connection blob for logs only
(`qualityGateAt`, last output). Do not skip a future request
because a previous probe passed.

## Placement

All logic in `backend/app/providers/grok_cli/`. Call it from grok-cli
connection selection in the proxy path. No provider-specific checks
in generic routers.

## Catalog storage

Models live in SQLAlchemy table ``provider_models`` (provider +
model_id, ``enabled``). Connections do not own the list. Fetch from
one live account writes that catalog; Clear deletes those rows.

These buttons edit the **provider catalog**, not connection blobs.
They do not run the 407 probe.

| Action | What it does |
|--------|----------------|
| **Fetch** | GET `/models` from one live account. Upsert ``provider_models``. Drop `grok-build`. |
| **Clear** | DELETE FROM ``provider_models`` WHERE provider. |
| **Disable** | ``enabled = false`` on that row. |
| **Delete** (one row) | Remove that catalog row (PATCH replace list). |

After Fetch, chat still uses `gcli/grok-4.6` for the quality gate even
if other ids remain on the list.

Grok CLI sets `SYNC_DISABLED_WITH_MODEL_LIST`: Fetch enables the
returned ids (so they are not stuck in Suggestions). Clear enables
all for alias `gcli` so disabled history cannot outlive an empty list.

If the list is empty (after Clear), grok-cli has no registered models
until Fetch or a manual add — chat `gcli/grok-4.6` still routes
(provider/model path does not require `models[]`).

## Out of scope

- Background worker
- Changing OAuth `referrer=grok-build` (not a model id)
- Mass-clear of existing 402 flags
- Probe on every user token / injecting into the user transcript
- Fetch running the 407 probe (account gate ≠ model list)
