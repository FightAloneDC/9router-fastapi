# Provider data model and PS chat

Date: 2026-08-15

## Problem

Model lists are duplicated on every connection JSON blob
(`provider_connections.data.models`). One provider has one catalog:
every account sees the same model ids. Disable/fetch/clear therefore
belongs at provider grain, not per connection.

Quota and chat cannot share that grain. Limits are usually per
account; some providers (Alibaba, Antigravity, and others not listed
here) split limits by model id on the same catalog. Request
parameters and response shapes differ per provider. Agent farm
clients (Hermes, Pi, Cline, Codex, Claude, …) speak a client dialect
and must not be rewritten per upstream.

## Goal

- One catalog table for all providers.
- Opaque per-connection quota storage; meaning is provider-specific.
- Chat transform stays in `providers/<id>/`.
- Client doors that are widely used today, including native Google.
- No new columns on `provider_connections`.

## Catalog

Table `provider_models` (already sketched in Alembic
`a9b0c1d2e3f4`):

| Column | Role |
|--------|------|
| `provider` | Provider id (`grok-cli`, `mistral`, …) |
| `model_id` | Upstream / catalog id |
| `type` | e.g. `llm` |
| `name` | Optional display name |
| `enabled` | Included in `/v1/models` when true |

Unique `(provider, model_id)`. Fetch, Clear, and Disable target
these rows. All connections of that provider share the list.

After backfill, `data.models` on a connection is not the source of
truth. Do not keep writing the catalog into every connection blob.

## Connections

`provider_connections` stays the account row: auth type, name,
email, priority, `is_active`, optional `proxy_pool_id`, JSON `data`.

`data` holds credentials, fingerprints, and health fields
(`lastError`, `errorCode`, `rateLimitedUntil`, model locks). It does
not own the model catalog.

## Quota

`quota_cache`: one row per `connection_id` (FK cascade). Columns
`plan`, `quotas` (JSON text), `limit_reached`, `fetched_at`.

The `quotas` array is opaque. The router stores and returns it.
`providers/<id>/quota.py` decides:

- account-wide vs per-model-id items
- sources (headers, billing API, `usage_history`, 429 body)
- exhausted vs model-gating vs dead

Do not add `connection_model_quotas`. Do not put a provider-name
list in a shared service. `QuotaItem` may exist for the quota UI;
handlers may fill a subset. `model_id` on an item is optional, not
a required schema for every provider.

Telemetry stays `usage_history` and `request_details` (raw JSON
payloads). No columns for temperature, effort, or Google
`generationConfig`.

## Chat (PS)

Inbound client doors **now** (widely used):

1. `/v1/chat/completions` — OpenAI-compat agents
2. `/v1/messages` — Anthropic / Claude Code
3. `/v1/responses` — Codex, grok-cli
4. Native Google `:generateContent` / `:streamGenerateContent` —
   Gemini CLI and Google clients. Today this exists only as
   **outbound** transform in the Gemini handler. It must also be a
   **client** door.

Not a closed enum in the database. A later door is a new router
plus a handler, not a `format` column.

Outbound wire is always PS: OpenAI chat, Anthropic messages,
OpenAI Responses, Google `generateContent`, Qoder COSY, and
anything else a handler implements. Example: Mistral
`transform.py` drops `max_context_size` and reasoning knobs unless
the model is Magistral, and maps `developer` → `system`. Agent
farm must not special-case Mistral.

The `/v1_*` routers resolve a connection, call the handler, HTTP
to upstream, persist logs. Provider `if grok` / `if claude` /
`if google` branches must not grow in those routers.

## Out of scope

- Literal-407 quality gate and phantom-write retry (already
  feature-flagged off).
- Extra client doors beyond the four above.
- New columns on `provider_connections`.
- Generalizing quota semantics in shared code.

## Success

- `/v1/models` and Fetch/Clear/Disable use `provider_models` only.
- Quota UI still works from `quota_cache` without knowing provider
  rules.
- Mistral (and peers) still sanitize in their handler.
- A native Google client can hit generateContent on 9Router without
  going through chat-completions first.
