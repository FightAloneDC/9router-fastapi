---
name: 9router-web-search
description: Web search via 9Router /v1/search using Tavily / Exa / Brave / Serper / SearXNG / Google PSE / You.com / Jina AI. Use when the user wants to search the web or look up current information.
---

# 9Router — Web Search

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/webSearch | jq '.data[].id'
```

## Endpoint

`POST $NINEROUTER_URL/v1/search`

| Field | Required | Notes |
|---|---|---|
| `model` or `provider` | yes | from `/v1/models/webSearch` |
| `query` | yes | search query |
| `max_results` | no | default 5 |
| `search_type` | no | `web` (default) / `news` |

## Examples

```bash
curl -X POST $NINEROUTER_URL/v1/search \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"tavily","query":"9Router open source","max_results":5}'
```

## Response shape

```json
{
  "provider": "tavily",
  "query": "9Router open source",
  "results": [
    { "title": "...", "url": "https://...", "snippet": "...", "position": 1 }
  ],
  "usage": { "queries_used": 1 }
}
```

## Quirks

- `jina-ai` / `jina` (also legacy `jina-search`): POST
  `https://s.jina.ai/`; unified `query` → body `q`;
  `country`→`gl`, `language`→`hl`, `max_results`→`num`.
  Same API key as embed/rerank/reader. Catalog row `search`.
