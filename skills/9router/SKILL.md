---
name: 9router
description: Entry point for 9Router FastAPI — local/remote AI gateway with OpenAI-compatible REST for chat, image, TTS, STT, embeddings, rerank, web search, web fetch. Use when the user mentions 9Router, NINEROUTER_URL, or wants AI without writing provider boilerplate. This skill covers setup + indexes capability skills; fetch the relevant capability SKILL.md from the URLs below when needed.
---

# 9Router

Self-hosted OpenRouter-style proxy. Clients send OpenAI-compatible
requests → 9Router resolves the model alias to an upstream provider →
forwards the request → returns the response.

## Setup

```bash
export NINEROUTER_URL="http://localhost:8013"   # prod compose (FastAPI + UI)
# export NINEROUTER_URL="http://localhost:9000" # host-dev API only
export NINEROUTER_KEY="sk-..."                  # Dashboard → Keys
```

All requests: `${NINEROUTER_URL}/v1/...` with header
`Authorization: Bearer ${NINEROUTER_KEY}` (omit if `requireApiKey` is off).
A dashboard JWT from `POST /auth/login` is also accepted on `/v1/*`.

Verify: `curl $NINEROUTER_URL/health` → `{"status":"ok"}`

## Discover models

```bash
curl $NINEROUTER_URL/v1/models                  # chat/LLM (default)
curl $NINEROUTER_URL/v1/models/image            # image-gen
curl $NINEROUTER_URL/v1/models/tts              # text-to-speech
curl $NINEROUTER_URL/v1/models/stt              # speech-to-text
curl $NINEROUTER_URL/v1/models/embedding        # embeddings
curl $NINEROUTER_URL/v1/models/rerank           # rerank
curl $NINEROUTER_URL/v1/models/webSearch        # web search
curl $NINEROUTER_URL/v1/models/webFetch         # web fetch
curl $NINEROUTER_URL/v1/models/imageToText      # vision
```

Use `data[].id` as the `model` field. Combos appear with `owned_by:"9router"`.

Response shape:
```json
{ "object": "list", "data": [
  { "id": "openai/gpt-4o", "object": "model", "owned_by": "openai", "type": "llm" },
  { "id": "cohere/rerank-english-v3.0", "object": "model", "owned_by": "cohere", "type": "rerank" }
]}
```

## Capability skills

When the user needs a specific capability, fetch that skill's `SKILL.md`:

| Capability | Raw URL |
|---|---|
| Chat / code-gen | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-chat/SKILL.md |
| Image generation | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-image/SKILL.md |
| Text-to-speech | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-tts/SKILL.md |
| Speech-to-text | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-stt/SKILL.md |
| Embeddings | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-embeddings/SKILL.md |
| Rerank | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-rerank/SKILL.md |
| Web search | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-web-search/SKILL.md |
| Web fetch (URL → markdown) | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-web-fetch/SKILL.md |

## Errors

- 401 → set/refresh `NINEROUTER_KEY` (Dashboard → Keys) or login JWT
- 400 missing `model` / `query` / `documents` → check the capability skill
- 503 no active connection → add or re-enable a provider account
