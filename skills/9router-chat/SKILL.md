---
name: 9router-chat
description: Chat / code generation via 9Router using OpenAI /v1/chat/completions, Anthropic /v1/messages, or /v1/responses with streaming and auto-fallback combos. Use when the user wants to ask an LLM, generate code, summarize text, or run prompts through 9Router.
---

# 9Router — Chat

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Endpoints

- `POST $NINEROUTER_URL/v1/chat/completions` — OpenAI format
- `POST $NINEROUTER_URL/v1/messages` — Anthropic format
- `POST $NINEROUTER_URL/v1/responses` — OpenAI Responses format

## Discover

```bash
curl $NINEROUTER_URL/v1/models | jq '.data[].id'
curl "$NINEROUTER_URL/v1/models/info?id=openai/gpt-4o"
```

Combos auto-fallback through multiple providers.

## OpenAI format

```bash
curl -X POST $NINEROUTER_URL/v1/chat/completions \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o","messages":[{"role":"user","content":"Hi"}],"stream":false}'
```

JS (OpenAI SDK):

```js
import OpenAI from "openai";
const client = new OpenAI({
  baseURL: `${process.env.NINEROUTER_URL}/v1`,
  apiKey: process.env.NINEROUTER_KEY,
});
const res = await client.chat.completions.create({
  model: "openai/gpt-4o",
  messages: [{ role: "user", content: "Hi" }],
  stream: true,
});
for await (const chunk of res)
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
```

## Anthropic format

```bash
curl -X POST $NINEROUTER_URL/v1/messages \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"an/claude-sonnet-4","max_tokens":1024,"messages":[{"role":"user","content":"Hi"}]}'
```

## Response shape

OpenAI (`/v1/chat/completions`):
```json
{ "id": "chatcmpl-...", "object": "chat.completion", "model": "openai/gpt-4o",
  "choices": [{ "index": 0, "message": { "role": "assistant", "content": "Hello!" }, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10 } }
```

Streaming (`stream:true`) emits SSE:
`data: {choices:[{delta:{content:"..."}}]}` … `data: [DONE]`.
