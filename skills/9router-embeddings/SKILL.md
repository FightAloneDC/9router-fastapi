---
name: 9router-embeddings
description: Generate vector embeddings via 9Router /v1/embeddings using OpenAI / Gemini / Mistral / Voyage / Nvidia / Jina embedding models for RAG, semantic search, similarity. Use when the user wants embeddings, vectors, RAG, or semantic search.
---

# 9Router — Embeddings

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/embedding | jq '.data[].id'
curl "$NINEROUTER_URL/v1/models/info?id=openai/text-embedding-3-small"
```

## Endpoint

`POST $NINEROUTER_URL/v1/embeddings`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/embedding` |
| `input` | yes | string OR array of strings |
| `encoding_format` | no | `float` (default) / `base64` |
| `dimensions` | no | OpenAI v3 only |

## Examples

```bash
curl -X POST $NINEROUTER_URL/v1/embeddings \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/text-embedding-3-small","input":["hello","world"]}'
```

## Response shape

```json
{ "object": "list", "model": "openai/text-embedding-3-small",
  "data": [
    { "object": "embedding", "index": 0, "embedding": [0.0123, -0.045] }
  ],
  "usage": { "prompt_tokens": 5, "total_tokens": 5 } }
```
