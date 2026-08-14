---
name: 9router-stt
description: Speech-to-text via 9Router /v1/audio/transcriptions using OpenAI Whisper / Groq / Gemini / Deepgram / AssemblyAI models. Use when the user wants to transcribe audio or convert speech to text.
---

# 9Router — Speech-to-Text

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/stt | jq '.data[].id'
```

## Endpoint

`POST $NINEROUTER_URL/v1/audio/transcriptions` (`multipart/form-data`)

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/stt` |
| `file` | yes | audio file (mp3, wav, m4a, webm, ogg, flac) |
| `language` | no | ISO-639-1 (e.g. `en`, `id`) |
| `response_format` | no | `json` (default) / `text` / `verbose_json` / `srt` / `vtt` |

## Examples

```bash
curl -X POST "$NINEROUTER_URL/v1/audio/transcriptions" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -F "model=openai/whisper-1" \
  -F "file=@audio.mp3" \
  -F "language=id"
```

Default response: `{ "text": "..." }`.
