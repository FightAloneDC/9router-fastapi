# 9Router — Agent Skills

Drop-in skills for any AI agent (Claude, Cursor, ChatGPT, custom SDK).
Copy a link below and paste it to your AI — it will fetch the skill and
use this 9Router instance.

> Tip: start with the **9router** entry skill — it covers setup and
> links to every capability skill.

## Skills

| Capability | Copy this link and paste it to your AI |
|---|---|
| **Entry / Setup** (start here) | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md |
| Chat / code-gen | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-chat/SKILL.md |
| Image generation | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-image/SKILL.md |
| Text-to-speech | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-tts/SKILL.md |
| Speech-to-text | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-stt/SKILL.md |
| Embeddings | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-embeddings/SKILL.md |
| Rerank | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-rerank/SKILL.md |
| Web search | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-web-search/SKILL.md |
| Web fetch (URL → markdown) | https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router-web-fetch/SKILL.md |

## How to use

```
Read this skill and use it: https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
```

Then ask normally — *"generate an image of a cat"*, *"rerank these docs"*, etc.

## Configure your shell once

```bash
export NINEROUTER_URL="http://localhost:8013"   # prod compose; host-dev API is :9000
export NINEROUTER_KEY="sk-..."                  # Dashboard → Keys (only if requireApiKey=true)
```

Verify: `curl $NINEROUTER_URL/health` → `{"status":"ok"}`.

## Links

- Source: https://github.com/FightAloneDC/9router-fastapi
- Dashboard (prod): http://localhost:8013
- Dashboard (host-dev UI): http://localhost:5173
