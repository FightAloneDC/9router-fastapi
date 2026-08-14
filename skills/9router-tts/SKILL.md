---
name: 9router-tts
description: Text-to-speech via 9Router /v1/audio/speech using OpenAI / ElevenLabs / Deepgram / Edge TTS / Google TTS voices. Use when the user wants to convert text to speech, generate audio, voiceover, or read text aloud.
---

# 9Router — Text-to-Speech

Requires `NINEROUTER_URL` (and `NINEROUTER_KEY` if auth enabled). See
https://raw.githubusercontent.com/FightAloneDC/9router-fastapi/refs/heads/main/skills/9router/SKILL.md
for setup.

## Discover

```bash
curl $NINEROUTER_URL/v1/models/tts | jq '.data[].id'
curl "$NINEROUTER_URL/v1/audio/voices?provider=edge-tts"
```

## Endpoint

`POST $NINEROUTER_URL/v1/audio/speech`

| Field | Required | Notes |
|---|---|---|
| `model` | yes | from `/v1/models/tts` (often `provider/voice`) |
| `input` | yes | text to speak |
| `voice` | sometimes | required when the model string has no voice |

## Examples

```bash
curl -X POST "$NINEROUTER_URL/v1/audio/speech" \
  -H "Authorization: Bearer $NINEROUTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/tts-1","input":"Hello world","voice":"alloy"}' \
  --output speech.mp3
```

Default response is raw audio bytes (`Content-Type: audio/mpeg` or similar).
