# Provider model catalog (SQL table)

Date: 2026-08-15 (updated 2026-08-18)

**Policy now:** the model catalog is a database table
(`provider_models`). Storing the list in each connection JSON blob
(`data.models`) is the old design and is **wrong**. Do not document
or implement blob catalogs as the happy path.

## Switch (PS, not a name list in routers)

`BaseProviderConfig.MODEL_CATALOG_TABLE = False` — legacy only.

Set `MODEL_CATALOG_TABLE = True` on the provider config. Helper:
`uses_model_catalog_table(provider_id)` via `Provider(id).config()`.

On as of 2026-08-18: **openrouter**, **groq**, **nvidia**,
**cerebras**, **mistral**, **alims-intl**, **cohere**, **morph**.

Everyone else still reading `data.models` is migration debt. Next
ordinary OpenAI-compat provider gets the flag on day one.

## Behavior

| Path | Flag on | Flag off (debt) |
|------|---------|-----------------|
| Fetch / set / clear | `provider_models` | `data.models` blob |
| `/v1/models` + proxy match | catalog rows | blobs |
| Chat body | unchanged | unchanged |

Quota is `quota_cache` + provider `quota.py`, not the blob.
Connection `data` keeps API keys and health only.

## Backfill

Alembic copies existing blob arrays into `provider_models`
(`ON CONFLICT DO NOTHING`). After that, blobs are not the source of
truth. Fetch must not write the catalog back into every connection.
