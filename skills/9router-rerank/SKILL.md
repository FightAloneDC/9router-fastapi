---
name: 9router-rerank
description: Rerank documents via 9Router /v1/rerank using Cohere / Jina / Voyage / Alims. Use when the user wants to score, reorder, or rank documents against a query for RAG or search.
---

# 9Router — Rerank

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

Score a query against a list of documents and get them back ordered by
relevance. Implemented providers: `cohere`, `jina_ai`, `voyage_ai`,
`alims-intl`.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/rerank | jq '.data[].id'
```

Use `data[].id` as `model` (for example `cohere/rerank-english-v3.0`
or just the provider id `cohere`).

## Endpoint

`POST $NINEROUTER_URL/v1/rerank`

| Field | Required | Notes |
|---|---|---|
| `model` or `provider` | yes | rerank provider / model id |
| `query` | yes | search query string |
| `documents` | yes | array of strings (or objects the provider accepts) |
| `top_n` | no | max results (default 10, max 100) |
| `return_documents` | no | include original document text |
| `language` | no | optional language code |
| `instruct` | no | extra instruction when the provider supports it |
| `provider_options` | no | provider-specific extras |

## Examples

```bash
curl -X POST $NINEROUTER_URL/v1/rerank \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cohere",
    "query": "how to reset a password",
    "documents": [
      "Click Forgot password on the login page.",
      "Our office is open 9 to 5.",
      "Update your profile photo in Settings."
    ],
    "top_n": 3,
    "return_documents": true
  }'
```

JS:

```js
const r = await fetch(`${process.env.NINEROUTER_URL}/v1/rerank`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.NINEROUTER_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    model: "jina_ai",
    query: "vector search ranking",
    documents: ["intro to BM25", "cross-encoder rerankers", "cookie recipe"],
    top_n: 2,
  }),
});
const { results } = await r.json();
console.log(results);
```

## Response shape

```json
{
  "provider": "cohere",
  "query": "how to reset a password",
  "results": [
    { "index": 0, "relevance_score": 0.91, "document": "Click Forgot password..." },
    { "index": 2, "relevance_score": 0.22 }
  ],
  "usage": { "queries_used": 1 },
  "metrics": { "response_time_ms": 180 },
  "errors": []
}
```

`index` is the position in the original `documents` array.
`relevance_score` is higher = more relevant.

## Provider quirks

| Provider | Notes |
|---|---|
| `cohere` | Native `POST /rerank`; default model `rerank-english-v2.0` if omitted |
| `jina_ai` | Jina reranker API |
| `voyage_ai` | Handler maps unified `top_n` → Voyage `top_k` (Voyage rejects `top_n`) |
| `jina_ai` | Native `top_n`; documented catalog (live `/models` is mixed inventory) |
| `alims-intl` | Alims international rerank |

Need a connection for that provider in the dashboard. 401/403 from
upstream follows the usual fallback / cooldown rules.
