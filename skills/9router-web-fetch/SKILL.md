---
name: 9router-web-fetch
description: Fetch URL → markdown / text / HTML via 9Router /v1/web/fetch using Firecrawl / Jina Reader / Tavily Extract / Exa Contents. Use when the user wants to scrape a webpage or convert a URL to markdown.
---

# 9Router — Web Fetch

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/webFetch | jq '.data[].id'
```

## Endpoint

`POST $NINEROUTER_URL/v1/web/fetch`

| Field | Required | Notes |
|---|---|---|
| `model` or `provider` | yes | from `/v1/models/webFetch` |
| `url` | yes | URL to extract |
| `format` | no | `markdown` (default) / `text` / `html` |
| `max_characters` | no | truncate output |

## Examples

```bash
curl -X POST $NINEROUTER_URL/v1/web/fetch \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"jina-reader","url":"https://example.com","format":"markdown"}'
```

## Response shape

```json
{
  "provider": "jina-reader",
  "url": "https://example.com",
  "title": "...",
  "content": { "format": "markdown", "text": "...", "length": 1234 }
}
```
