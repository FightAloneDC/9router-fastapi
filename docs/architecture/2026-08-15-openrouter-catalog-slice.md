# OpenRouter catalog slice

Date: 2026-08-15

One provider only: **openrouter** (generic OpenAI-compat). Grok,
Qoder, Mistral, Gemini stay on connection `data.models`.

## Switch (PS, not a name list in routers)

`BaseProviderConfig.MODEL_CATALOG_TABLE = False`

`OpenrouterConfig.MODEL_CATALOG_TABLE = True`

Helper: `uses_model_catalog_table(provider_id) -> bool` reads that
flag via `Provider(id).config()`.

## Behavior

| Path | OpenRouter | Others |
|------|------------|--------|
| Fetch / set / clear models | `provider_models` | `data.models` blobs (main) |
| `/v1/models` + proxy match | catalog rows | blobs |
| Chat body | unchanged (OpenAI) | unchanged |

No Google door. No quota rewrite. No mass provider edits.

Alembic: model first, then `--autogenerate`. Backfill **only**
`provider = 'openrouter'` from existing blobs.

## Later

Turn the same flag on for the next ordinary OpenAI-compat provider.
Keep unique providers last.
