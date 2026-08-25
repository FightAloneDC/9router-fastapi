# Voyage AI provider flow

Source of truth: files in this folder.

## Files

| File | Role |
|------|------|
| `config.py` | Identity, embedding/rerank service kinds, SQL catalog flag, model type overrides |
| `models.py` | Hardcoded catalog from official Voyage model docs |
| `handler.py` | Embedding validation, catalog fetch, and native rerank request |
| `quota.py` | Summary card + modal: free-token grants and RPM/TPM |

## Identity

```
PROVIDER_NAME        = Voyage AI
PROVIDER_ID          = voyage-ai
ALIAS                = voyage
BASE_URL             = https://api.voyageai.com/v1
SERVICE_KINDS        = embedding, rerank
MODEL_CATALOG_TABLE  = True
```

## Model catalog

Voyage does not publish a list-models API. Official reference
(https://docs.voyageai.com/reference/, retrieved 2026-08-25) only
has POST inference endpoints: `/embeddings`, `/multimodalembeddings`,
`/contextualizedembeddings`, and `/rerank`. A previous fetch called
`GET {BASE_URL}/models` and the browser showed Axios 404 because that
upstream status was forwarded.

Catalog ids come from official model pages (retrieved 2026-08-25):

- https://docs.voyageai.com/docs/embeddings.md
- https://docs.voyageai.com/docs/contextualized-chunk-embeddings.md
- https://docs.voyageai.com/docs/multimodal-embeddings.md
- https://docs.voyageai.com/docs/reranker.md

Current models plus older ids still marked accessible live in
`config.MODEL_TYPE_OVERRIDES`. `models.HARDCODED_MODELS` is
built from that map (includes `voyage-code-2`). Deprecated
text-embedding ids and Hugging Face-only `voyage-4-nano` are
omitted. Contextualized and
multimodal ids are typed `embedding` so they appear on the embedding
page; this app still proxies text embeddings to `/embeddings` and
rerank to `/rerank`. Fetch stores the catalog in `provider_models`,
not the connection `data` blob.

## Proxy paths

- Embeddings use the standard `/embeddings` path and Bearer auth.
- OpenAI-compat clients may send `dimensions`; the handler maps
  that to Voyage `output_dimension` and drops `dimensions`
  (https://docs.voyageai.com/reference/embeddings-api.md).
- Rerank uses `{baseUrl}/rerank`, with default model `rerank-lite-1`.
- Unified `/v1/rerank` clients send Cohere-style `top_n`; the
  handler maps that to Voyage `top_k` and never forwards `top_n`
  (https://docs.voyageai.com/reference/reranker-api).
- Rerank responses are normalized from Voyage `data` items to `results`.
- Usage observation has no upstream quota-header implementation.

## Quota tracker

`USES_UPSTREAM = False`. Voyage publishes two units, both on
the Quota Tracker:

1. **Free-token grant** (https://docs.voyageai.com/docs/pricing.md)
   — lifetime, per current model, per account. 200 million tokens
   for `voyage-4-large`, `voyage-4`, `voyage-4-lite`,
   `voyage-context-4`, `voyage-code-4`, both multimodal ids, and
   `rerank-2.5` / `rerank-2.5-lite` / `rerank-2` / `rerank-2-lite`.
   50 million for `voyage-finance-2`, `voyage-law-2`,
   `voyage-code-2`. Older models have **none**. Exhausting the
   grant starts billing; the API does not 429. Batch API does
   not consume the grant. 150B multimodal pixels are not tracked.
2. **RPM + TPM** (https://docs.voyageai.com/docs/rate-limits.md)
   — per model, whole organization, usage tier 1/2/3
   (1× / 2× / 3× billed spend). Over-limit is HTTP 429.
   Remaining is on the Voyage dashboard, not in API headers.

### How `used` is computed

Embeddings/rerank responses expose Voyage
`usage.total_tokens` (multimodal may also send `text_tokens`,
`image_pixels`, `video_pixels`). The proxy stores
`total_tokens` into `usage_history.prompt_tokens` (OpenAI-compat
columns) and keeps the raw object in `tokens`. Quota then sums
`prompt_tokens + completion_tokens` per model.

**List card (`fetch`)** — three finite bars using free-tier /
tier-1 **maxima** (not 0/∞):

| Bar | `used` | `total` |
|-----|--------|---------|
| `free tokens` | this key, all-time tokens | max `FREE_TOKENS` (200M) |
| `RPM` | this key, last 60s requests | max table RPM (2000) |
| `TPM` | this key, last 60s tokens | max table TPM (16M) |

Per-model 50M grants and lower TPM rows stay in the modal.

- **Modal RPM** = count of `usage_history` rows for this connection
  + model in the **last 60 seconds** (rolling window).
- **Modal TPM** = sum of those tokens in the same window.
- **Modal free tokens** = all-time token sum for this connection +
  model vs that model's `FREE_TOKENS`.

There is no Voyage remaining-header to poll. `reset_at` on RPM/TPM
bars is a UI hint (`now + 60s`), not a clock-aligned minute.
Quota Tracker auto-refresh (and list fetch for
`USES_UPSTREAM=False`) re-queries the rolling window — requests
older than 60s drop out of RPM/TPM `used` automatically. Sibling
org keys and true remaining free tokens stay dashboard-only.

The **Model details** modal (`GET /usage/{id}?detail=models`, not
cached) groups by model: `{id} free tokens`, `{id} RPM`,
`{id} TPM` together. Ids missing from `RATE_LIMITS`
(`voyage-3`, `voyage-3-lite`) are omitted.

Tier-1 RPM is 2000 on every listed model. TPM groups:

| TPM | Models |
|-----|--------|
| 16M | `voyage-4-lite`, `voyage-3.5-lite` |
| 8M | `voyage-4`, `voyage-code-4`, `voyage-3.5` |
| 4M | `rerank-2.5-lite`, `rerank-2-lite`, `rerank-lite-1` |
| 3M | `voyage-4-large`, `voyage-context-4`, `voyage-3-large`, `voyage-context-3`, `voyage-code-3`, 1 & 2 series embeddings |
| 2M | `voyage-multimodal-3.5`, `voyage-multimodal-3`, `rerank-2.5`, `rerank-2`, `rerank-1` |

This host does not know billed spend, so the table stays tier 1.
Tier 2/3, project limits, sibling keys, and remaining free
tokens on the org are dashboard-only
(https://dashboard.voyageai.com/organization/rate-limits).

Voyage units are not another vendor's: no `x-ratelimit-*`
headers, no 40 RPM/key, no `:free` IP, no TPD plan split, no
1000 calls/month, no embed IPM, no 200 calls/month, no credits
GET. The card/modal split is UI density, not copied quotas.
