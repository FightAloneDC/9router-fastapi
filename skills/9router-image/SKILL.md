---
name: 9router-image
description: Generate images via 9Router /v1/images/generations using OpenAI / Gemini Imagen / DALL-E / FLUX / MiniMax / SDWebUI models. Use when the user wants to create, generate, draw, or render an image or text-to-image.
---

# 9Router — Image Generation

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/image | jq '.data[].id'
curl "$NINEROUTER_URL/v1/models/info?id=openai/dall-e-3"
```

## Endpoint

`POST $NINEROUTER_URL/v1/images/generations`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/image` |
| `prompt` | yes | image description |
| `n` | no | count (provider-dependent) |
| `size` | no | `1024x1024`, `1792x1024`, … |
| `quality` | no | `standard` / `hd` (OpenAI) |
| `response_format` | no | `url` (default) or `b64_json` |

## Examples

```bash
curl -X POST "$NINEROUTER_URL/v1/images/generations" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/dall-e-3","prompt":"watercolor mountains at sunrise","size":"1024x1024"}'
```

## Response shape

```json
{ "created": 1735000000, "data": [{ "url": "https://..." }] }
```

`response_format=b64_json` returns `{ "data": [{ "b64_json": "iVBORw0K..." }] }`.
