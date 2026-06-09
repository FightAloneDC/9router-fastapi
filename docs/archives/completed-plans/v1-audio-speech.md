# Plan: POST /v1/audio/speech (TTS)

**Status:** 🟢 Backend feature-complete (2026-05-23) — Iterasi 1+2+3 shipped. All cloud-provider adapters (14 total) wired and code-tested. Gemini live-tested with real audio output. **Pending:** live testing for 11 adapters with real API keys, plus optional Phase 5 frontend TTS playground (originally marked "no changes required" but reconsidered in Iterasi 3 notes).
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`
**Original source:** `~/dev/9router/src/app/api/v1/audio/speech/route.js` → `src/sse/handlers/tts.js` → `open-sse/handlers/ttsCore.js`
**Estimated effort:** Medium — more complex than embeddings due to binary responses,
multiple provider adapters with wildly different APIs, and model format parsing.

**Iteration plan:**
| Iterasi | Scope | Status |
|---|---|---|
| 1 | Phase 1 (parser) + Phase 4 (PCM→WAV util) + Phase 2 Group A only + Phase 3 (route handler) + structural smoke tests | ✅ Done (2026-05-23) |
| 2 | Group B-1 adapters: gemini, elevenlabs, minimax (+minimax-cn), openrouter | ✅ Done (2026-05-23) — **Gemini live-tested, returned 169KB valid WAV** |
| 3 | Group B-2 simple binary: deepgram, nvidia, huggingface, inworld, cartesia, playht | ✅ Done (2026-05-23) — 20 smoke checks pass; live testing pending API keys |
| 4 (optional) | Frontend TTS playground in `MediaProviderDetailPage.jsx` — model/voice dropdowns, `<audio>` playback, download button | ⏸️ Not started |
| Deferred | Group C local: edge-tts, coqui, tortoise, google-tts, local-device + AWS Polly | 📌 Out of scope |

---

## Progress Tracker (Phase-by-Phase)

| Phase | Component | Status | Evidence |
|---|---|---|---|
| **Phase 1** | `parse_tts_model()` in `backend/app/services/proxy.py` | ✅ Done | `proxy.py:594` — strict no-defaults parser, splits on LAST slash |
| **Phase 2.1** | OpenAI-compatible adapter (Group A: openai, siliconflow) | ✅ Done | `tts_adapters.py:76` `tts_openai_compatible()` |
| **Phase 2.2 (A)** | Hyperbolic adapter | ✅ Done | `tts_adapters.py:118` `tts_hyperbolic()` |
| **Phase 2.2 (B-1)** | Gemini adapter (PCM→WAV) | ✅ Done — **live-tested** | `tts_adapters.py:168` — returned 169KB WAV @ 24kHz mono |
| **Phase 2.2 (B-1)** | ElevenLabs adapter | ✅ Done — code only | `tts_adapters.py:259` |
| **Phase 2.2 (B-1)** | MiniMax (+ minimax-cn alias) adapter | ✅ Done — code only | `tts_adapters.py:306` |
| **Phase 2.2 (B-1)** | OpenRouter SSE adapter | ✅ Done — code only | `tts_adapters.py:392` — dispatched OK, upstream model rejection seen |
| **Phase 2.2 (B-2)** | Deepgram adapter | ✅ Done — code only | `tts_adapters.py:480` |
| **Phase 2.2 (B-2)** | NVIDIA adapter | ✅ Done — code only | `tts_adapters.py:527` |
| **Phase 2.2 (B-2)** | HuggingFace adapter | ✅ Done — code only | `tts_adapters.py:567` |
| **Phase 2.2 (B-2)** | Inworld adapter | ✅ Done — code only | `tts_adapters.py:609` |
| **Phase 2.2 (B-2)** | Cartesia adapter | ✅ Done — code only | `tts_adapters.py:650` |
| **Phase 2.2 (B-2)** | PlayHT adapter | ✅ Done — code only | `tts_adapters.py:700` |
| **Phase 2.3** | `TTS_ADAPTERS` dispatch table | ✅ Done | `tts_adapters.py:757` — 14 entries |
| **Phase 3** | Route handler `POST /v1/audio/speech` | ✅ Done | `v1_proxy.py:441` — alias resolution, fallback loop, `_FIXED_URL_PROVIDERS` set, `language` passthrough |
| **Phase 4** | `pcm_to_wav()` utility | ✅ Done | `tts_adapters.py:31` |
| **Phase 5** | Frontend changes | ⏸️ Deferred to Iterasi 4 (optional) | Original plan said "no changes required"; Iterasi 3 notes propose a TTS playground in `MediaProviderDetailPage.jsx` |
| **Phase 6.1** | Manual curl tests (8 scripted) | 🟡 Partial | Tests 1-4 (validation): all pass. Test 5 (Gemini live): ✅ pass. Tests 6-8 (ElevenLabs/OpenRouter/no-conn): structural only — need real API keys for live verification |
| **Phase 6.2** | Verify in running app (regression) | ✅ Done | Frontend MediaProvidersPage still renders TTS providers correctly |
| **Phase 6.3** | Regression check on `/v1/chat/completions` | ✅ Done | Chat endpoint untouched |
| **Phase 7** | Update `docs/porting-status.md` + `docs/plans/v1-proxy-endpoints.md` + this file | 🟡 Partial | This file: tracker updated. `porting-status.md` and parent plan: need verification of latest state |

**Live-testing checklist (needs API keys, all currently pending):**

| Provider | Status | Test command |
|---|---|---|
| openai | ⏸️ pending | `curl ... -d '{"model":"openai/gpt-4o-mini-tts/alloy","input":"hi"}'` |
| siliconflow | ⏸️ pending | `curl ... -d '{"model":"siliconflow/FunAudioLLM/CosyVoice2-0.5B/alex","input":"hi"}'` |
| hyperbolic | ⏸️ pending | `curl ... -d '{"model":"hyperbolic/melo-tts/EN-US","input":"hi"}'` |
| gemini | ✅ **live-verified** | Returned 169530 bytes valid WAV (RIFF/PCM/16-bit/mono/24kHz) |
| elevenlabs | ⏸️ pending | `curl ... -d '{"model":"elevenlabs/eleven_multilingual_v2/Rachel","input":"hi"}'` |
| minimax | ⏸️ pending | `curl ... -d '{"model":"minimax/speech-2.5-hd-preview/English_expressive_narrator","input":"hi"}'` |
| minimax-cn | ⏸️ pending | (alias for minimax — same as above with `minimax-cn/...`) |
| openrouter | 🟡 dispatched, upstream rejected | adapter wiring works; pick a real TTS-capable OR model to verify audio output |
| nvidia | ⏸️ pending | `curl ... -d '{"model":"nvidia/magpie-tts-multilingual/English-US.Female-1","input":"hi"}'` |
| deepgram | ⏸️ pending | `curl ... -d '{"model":"deepgram/aura-asteria-en/aura-asteria-en","input":"hi"}'` |
| huggingface | ⏸️ pending | needs body-level `tts_model`/`voice` fields (model ID contains `/`) |
| inworld | ⏸️ pending | `curl ... -d '{"model":"inworld/inworld-tts-1.5-mini/Alex","input":"hi"}'` |
| cartesia | ⏸️ pending | `curl ... -d '{"model":"cartesia/sonic-2/<voice-id>","input":"hi"}'` |
| playht | ⏸️ pending | needs `userId:apiKey` colon-joined as the saved api_key; voice = S3 manifest URL |

---

## What This Does

Adds an OpenAI-compatible TTS (text-to-speech) endpoint to the FastAPI proxy.
Clients send text + model (which encodes provider + voice), 9Router resolves
the provider, forwards to the upstream TTS API, and returns binary audio.

```
Client → POST /v1/audio/speech { model: "openai/gpt-4o-mini-tts/alloy", input: "Hello" }
           ↓
       parse model → provider "openai", ttsModel "gpt-4o-mini-tts", voice "alloy"
           ↓
       DB lookup → find active connection with API key
           ↓
       POST https://api.openai.com/v1/audio/speech { model, voice, input }
           ↓
       return binary audio (mp3/wav/opus) with correct Content-Type
```

---

## Key Difference From Embeddings

TTS is fundamentally different from chat/embeddings:

1. **Binary response** — upstream returns raw audio bytes, not JSON.
   Must forward with correct `Content-Type: audio/{format}` header.

2. **Model format is `ttsModel/voice`** — the `model` field encodes BOTH the
   model AND the voice. Examples:
   - `openai/gpt-4o-mini-tts/alloy` → provider=openai, model=gpt-4o-mini-tts, voice=alloy
   - `gemini/gemini-2.5-flash-preview-tts/Kore` → provider=gemini, model=gemini-2.5-flash-preview-tts, voice=Kore
   - `openai/alloy` → provider=openai, model=default(tts-1), voice=alloy

3. **Provider-specific adapters** — each TTS provider has a COMPLETELY different
   API (URL, headers, body format, response format). Not just a path swap.

4. **`response_format` query param** — client can request `mp3` (default), `wav`,
   `opus`, `aac`, or `json` (returns base64-encoded audio in JSON body).

5. **`language` field** — optional, used by Gemini TTS to set speech language.

---

## Supported Providers & Their APIs

### Group A: OpenAI-Compatible (simplest — standard `/audio/speech` endpoint)

These all use the same body format: `{ model, voice, input, response_format }`.

| Provider   | Upstream URL                                   | Auth           | Notes                    |
|------------|-----------------------------------------------|----------------|--------------------------|
| openai     | https://api.openai.com/v1/audio/speech        | Bearer         | Default TTS provider     |
| siliconflow | https://api.siliconflow.cn/v1/audio/speech    | Bearer         | Same format              |
| hyperbolic | https://api.hyperbolic.xyz/v1/audio/generation| Bearer         | Body: `{ text }`, response: `{ audio: base64 }` |

### Group B: Provider-Specific Adapters (need custom logic)

| Provider     | Upstream URL                                  | Auth              | Body Format                                    | Response        |
|-------------|----------------------------------------------|-------------------|------------------------------------------------|-----------------|
| openrouter  | https://openrouter.ai/api/v1/chat/completions | Bearer            | Chat completions with `modalities: ["text","audio"]` | SSE stream → accumulate base64 chunks |
| gemini      | https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key} | query param key | `contents + generationConfig.responseModalities: ["AUDIO"]` | JSON → PCM base64, wrap as WAV |
| elevenlabs  | https://api.elevenlabs.io/v1/text-to-speech/{voice} | xi-api-key    | `{ text, model_id }`                            | Binary audio    |
| minimax     | https://api.minimax.io/v1/t2a_v2             | Bearer            | `{ model, text, stream: false, output_format: "hex", voice_setting: {...} }` | JSON → hex audio |
| deepgram    | https://api.deepgram.com/v1/speak?model={model} | Token           | `{ text }`                                      | Binary audio    |
| nvidia      | https://integrate.api.nvidia.com/v1/audio/speech | Bearer         | `{ input: { text }, voice, model }`             | Binary audio    |
| huggingface | https://api-inference.huggingface.co/models/{model} | Bearer      | `{ inputs: text }`                              | Binary audio    |
| inworld     | https://api.inworld.ai/tts/v1/voice           | Basic auth        | `{ text, voiceId, modelId, audioConfig }`       | JSON → audioContent base64 |
| cartesia    | https://api.cartesia.ai/tts/bytes             | X-API-Key         | `{ model_id, transcript, voice, output_format }` | Binary audio  |
| playht      | https://api.play.ht/api/v2/tts/stream         | X-USER-ID + Bearer | `{ text, voice, voice_engine }`               | Binary audio    |

### Group C: Local/NoAuth (localhost services)

| Provider      | Upstream URL              | Auth  | Notes                    |
|--------------|--------------------------|-------|--------------------------|
| edge-tts     | local (edge-tts lib)      | None  | Runs locally, no network |
| local-device | local (OS TTS)            | None  | System TTS               |
| google-tts   | local (Google TTS lib)    | None  | Runs locally             |
| coqui        | http://localhost:5002/api/tts | None | Local Coqui TTS server |
| tortoise     | http://localhost:5000/api/tts | None | Local Tortoise TTS server |

---

## Request / Response Format

**Request:**
```bash
POST /v1/audio/speech?response_format=mp3
Authorization: Bearer <jwt_or_api_key>
Content-Type: application/json

{
  "model": "openai/gpt-4o-mini-tts/alloy",
  "input": "Hello, welcome to 9Router!",
  "voice": "alloy",
  "response_format": "mp3",
  "speed": 1.0,
  "language": "en"
}
```

- `model` (required) — format: `{alias}/{ttsModel}/{voice}` or `{alias}/{voice}`
- `input` (required) — text to synthesize
- `voice` (optional) — voice override (if not in model string)
- `response_format` (optional) — `mp3` (default), `wav`, `opus`, `aac`, `json`
- `speed` (optional) — playback speed, passed through
- `language` (optional) — language hint (used by Gemini)

**Response (binary — default):**
```
HTTP/1.1 200 OK
Content-Type: audio/mpeg
Content-Length: 48000

[raw audio bytes]
```

**Response (json format):**
```json
{
  "audio": "UklGRiQ...",
  "format": "mp3"
}
```

---

## Phase 1 — Backend: Parse Model String

The model string for TTS is more complex than chat. Add a parser in
`backend/app/services/proxy.py`:

```python
def parse_tts_model(model_str: str, provider: str) -> tuple[str, str]:
    """
    Parse TTS model string into (tts_model, voice).
    
    Formats:
      - "openai/gpt-4o-mini-tts/alloy" → after alias strip → "gpt-4o-mini-tts" + "alloy"
      - "openai/alloy" → after alias strip → "gpt-4o-mini-tts" (default) + "alloy"
      - "gemini/gemini-2.5-flash-preview-tts/Kore" → "gemini-2.5-flash-preview-tts" + "Kore"
      - "elevenlabs/eleven_multilingual_v2/Rachel" → "eleven_multilingual_v2" + "Rachel"
    
    Default TTS models per provider:
      openai: gpt-4o-mini-tts
      gemini: gemini-2.5-flash-preview-tts
      elevenlabs: eleven_multilingual_v2
      minimax: speech-2.8-hd
    """
    DEFAULT_MODELS = {
        "openai": "gpt-4o-mini-tts",
        "gemini": "gemini-2.5-flash-preview-tts",
        "elevenlabs": "eleven_multilingual_v2",
        "minimax": "speech-2.8-hd",
        "deepgram": "aura-asteria-en",
        "nvidia": "fastpitch",
        "inworld": "inworld-tts-1.5-mini",
        "hyperbolic": "melo-tts",
    }
    
    parts = model_str.split("/")
    if len(parts) >= 2:
        tts_model = parts[0]
        voice = parts[1]
        return tts_model, voice
    elif len(parts) == 1:
        return DEFAULT_MODELS.get(provider, ""), parts[0]
    return DEFAULT_MODELS.get(provider, ""), "alloy"
```

---

## Phase 2 — Backend: TTS Provider Adapters

Create `backend/app/services/tts_adapters.py` — one function per provider group.

### 2.1 Base adapter (OpenAI-compatible providers)

```python
async def tts_openai_compatible(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
) -> httpx.Response:
    """Handle OpenAI-compatible TTS providers (openai, siliconflow, etc.)."""
    body = {
        "model": tts_model,
        "voice": voice,
        "input": input_text,
        "response_format": response_format,
    }
    return await client.post(
        f"{base_url}/audio/speech",
        json=body,
        headers=headers,
    )
```

### 2.2 Provider-specific adapters

Each returns `(audio_bytes: bytes, content_type: str)` or raises an error.

**Gemini** — most complex (PCM → WAV conversion, query param auth):
```python
async def tts_gemini(client, api_key, tts_model, voice, input_text, language):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_model}:generateContent?key={api_key}"
    body = {
        "contents": [{"parts": [{"text": f"Say: {input_text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    resp = await client.post(url, json=body)
    # Extract base64 PCM, wrap as WAV
    data = resp.json()
    b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    wav_bytes = pcm_to_wav(base64.b64decode(b64), sample_rate=24000)
    return wav_bytes, "audio/wav"
```

**OpenRouter** — chat completions with audio modality (SSE stream):
```python
async def tts_openrouter(client, api_key, tts_model, voice, input_text):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": tts_model,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "wav"},
        "stream": True,
        "messages": [{"role": "user", "content": input_text}],
    }
    # Stream SSE, accumulate audio data chunks from delta.audio.data
    chunks = []
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and line != "data: [DONE]":
                json_data = json.loads(line[6:])
                audio_data = json_data.get("choices", [{}])[0].get("delta", {}).get("audio", {}).get("data")
                if audio_data:
                    chunks.append(audio_data)
    audio_bytes = base64.b64decode("".join(chunks))
    return audio_bytes, "audio/wav"
```

**MiniMax** — hex-encoded audio in JSON response:
```python
async def tts_minimax(client, api_key, base_url, tts_model, voice, input_text):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": tts_model or "speech-2.8-hd",
        "text": input_text,
        "stream": False,
        "language_boost": "auto",
        "output_format": "hex",
        "voice_setting": {"voice_id": voice or "English_expressive_narrator", "speed": 1, "vol": 1, "pitch": 0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
    }
    resp = await client.post(base_url, json=body, headers=headers)
    data = resp.json()
    hex_audio = data["data"]["audio"]
    return bytes.fromhex(hex_audio), "audio/mpeg"
```

**ElevenLabs** — voice ID in URL path:
```python
async def tts_elevenlabs(client, api_key, tts_model, voice, input_text):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {"text": input_text, "model_id": tts_model or "eleven_multilingual_v2"}
    resp = await client.post(url, json=body, headers=headers)
    return resp.content, "audio/mpeg"
```

**Simple binary providers** (deepgram, nvidia, huggingface, cartesia, playht):
```python
async def tts_simple_binary(client, base_url, headers, body, output_format="mpeg"):
    resp = await client.post(base_url, json=body, headers=headers)
    return resp.content, f"audio/{output_format}"
```

### 2.3 Dispatch table

```python
TTS_ADAPTERS = {
    "openai": tts_openai_compatible,
    "siliconflow": tts_openai_compatible,
    "gemini": tts_gemini,
    "openrouter": tts_openrouter,
    "minimax": tts_minimax,
    "minimax-cn": tts_minimax,
    "elevenlabs": tts_elevenlabs,
    "hyperbolic": tts_hyperbolic,
    # Simple binary adapters dispatched by ttsConfig
    "deepgram": tts_deepgram,
    "nvidia": tts_nvidia,
    "huggingface": tts_huggingface,
    "inworld": tts_inworld,
    "cartesia": tts_cartesia,
    "playht": tts_playht,
    # Local/noAuth
    "edge-tts": tts_edge_tts,  # needs local edge-tts or skip
    "coqui": tts_coqui,
    "tortoise": tts_tortoise,
}
```

---

## Phase 3 — Backend: Add `/v1/audio/speech` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.post("/audio/speech")
async def audio_speech(
    request: Request,
    response_format: str = Query("mp3"),
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """OpenAI-compatible TTS proxy."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model_str = body.get("model")
    input_text = body.get("input")
    if not model_str:
        raise HTTPException(status_code=400, detail="Missing required field: model")
    if not input_text:
        raise HTTPException(status_code=400, detail="Missing required field: input")

    # Parse provider from model string
    if "/" not in model_str:
        raise HTTPException(status_code=400, detail="Model must be in 'provider/model/voice' format")

    provider_name, model_remainder = model_str.split("/", 1)
    provider_id = _resolve_provider_alias(provider_name)

    # DB lookup: find active connection for this provider
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == provider_id, ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()

    if not connections:
        raise HTTPException(status_code=503, detail=f"No connection for provider: {provider_id}")

    # Parse tts_model and voice from model_remainder
    tts_model, voice = parse_tts_model(model_remainder, provider_id)

    # Try each connection (fallback loop)
    last_error = None
    for conn in connections:
        data = json.loads(conn.data) if conn.data else {}
        api_key = data.get("apiKey", "")
        base_url = data.get("baseUrl") or PROVIDER_DEFAULTS.get(provider_id, {}).get("baseUrl", "")

        try:
            audio_bytes, content_type = await TTS_ADAPTERS[provider_id](
                client=async_client,
                base_url=base_url,
                api_key=api_key,
                tts_model=tts_model,
                voice=voice,
                input_text=input_text,
                response_format=response_format,
            )

            # json format: return base64
            if response_format == "json":
                return JSONResponse(content={
                    "audio": base64.b64encode(audio_bytes).decode(),
                    "format": content_type.split("/")[-1],
                })

            return Response(content=audio_bytes, media_type=content_type)

        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(status_code=502, detail=last_error or "All TTS providers failed")
```

---

## Phase 4 — Backend: PCM → WAV Utility

**File:** `backend/app/services/tts_adapters.py`

Gemini returns raw PCM 16-bit mono @ 24kHz. Need a WAV header wrapper:

```python
import struct

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM data in a WAV header."""
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm_data)
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + data_size, b'WAVE',
        b'fmt ', 16, 1, channels, sample_rate, byte_rate, block_align, bits,
        b'data', data_size,
    )
    return header + pcm_data
```

---

## Phase 5 — Frontend: No Changes Required

The `/v1/audio/speech` endpoint is a pure API endpoint. No UI changes needed.

The MediaProvidersPage already shows TTS providers. The ProviderDetailPage
already handles adding connections for TTS providers. Nothing to change.

**Optional future enhancement:** Add a "Test TTS" button in ProviderDetailPage
for TTS providers. Out of scope.

---

## Phase 6 — Testing

### 6.1 Manual curl tests

Get token first:
```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — OpenAI TTS (happy path, binary response):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini-tts/alloy", "input": "Hello from 9Router!"}' \
  --output test.mp3 -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```
Expected: HTTP 200, file ~10-50KB, playable as MP3.

**Test 2 — OpenAI TTS (JSON response):**
```bash
curl -s -X POST "http://localhost:9000/v1/audio/speech?response_format=json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/tts-1/alloy", "input": "Testing JSON format"}' \
  | jq '{audio_len: (.audio | length), format}'
```
Expected: `audio_len > 1000`, `format: "mp3"`.

**Test 3 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello"}' | jq .
```
Expected: `400` with `"Missing required field: model"`.

**Test 4 — Missing input (400):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/alloy"}' | jq .
```
Expected: `400` with `"Missing required field: input"`.

**Test 5 — Gemini TTS (PCM → WAV conversion):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini/gemini-2.5-flash-preview-tts/Kore", "input": "Hello from Gemini!"}' \
  --output test_gemini.wav -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```
Expected: WAV file, header starts with `RIFF....WAVE`.

**Test 6 — ElevenLabs TTS:**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "elevenlabs/eleven_multilingual_v2/Rachel", "input": "Hello from ElevenLabs!"}' \
  --output test_el.mp3 -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```

**Test 7 — OpenRouter TTS (SSE stream → accumulate):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openrouter/openai/gpt-4o-mini-tts/alloy", "input": "Hello from OpenRouter!"}' \
  --output test_or.wav -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```

**Test 8 — No connection for provider (503):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "nonexistent/voice", "input": "Hello"}' | jq .
```
Expected: `503` with `"No connection for provider: nonexistent"`.

### 6.2 Verify in running app

1. Open http://localhost:5173
2. Navigate to Media Providers → Text to Speech
3. Confirm TTS providers still display correctly — no regressions
4. Check Console Log page — curl requests should appear

### 6.3 Regression check

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 7 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/audio/speech` from "Not Yet Ported" to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 2 as ✅.
3. **`docs/plans/v1-audio-speech.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Local providers (edge-tts, coqui, tortoise, google-tts, local-device) | These require local services running. Skip in Phase 1 — add later as separate task. Focus on cloud providers first. |
| OpenRouter audio streaming | Complex SSE parsing. Must accumulate base64 chunks from `delta.audio.data`. If this fails, return clear error. |
| Gemini PCM → WAV | Must wrap raw PCM in WAV header with correct sample rate (24kHz). Validate the WAV header is correct. |
| MiniMax hex decoding | Response returns hex-encoded audio in JSON. Must decode hex → binary. Handle edge cases (empty hex, odd-length). |
| AWS Polly | Uses AWS SigV4 auth — complex signing. Skip in Phase 1, add later. |
| Speed param | OpenAI accepts `speed` (0.25-4.0). Not all providers support it. Pass through where supported, ignore elsewhere. |
| `response_format` param | Must be passed as query param (`?response_format=mp3`) per OpenAI spec. Some providers accept it in body instead. |
| Voice list endpoint | `/v1/audio/voices` is a separate endpoint (see parent plan). Does not block this. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/tts_adapters.py` | NEW — TTS provider adapters, PCM→WAV utility |
| `backend/app/services/proxy.py` | Add `parse_tts_model()` helper |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/audio/speech` handler |
| `docs/porting-status.md` | Move TTS endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 2 done |
| `docs/plans/v1-audio-speech.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies (httpx already installed).

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Low | Same pattern as embeddings — parse, resolve, forward |
| Model parsing | Low | Simple string splitting with defaults |
| OpenAI-compatible adapters | Low | Standard body format, binary response |
| Gemini adapter | Medium | PCM → WAV conversion, query param auth |
| OpenRouter adapter | High | SSE stream parsing, base64 chunk accumulation |
| MiniMax adapter | Medium | JSON response with hex-encoded audio |
| ElevenLabs adapter | Low | Voice ID in URL path, simple body |
| Error handling | Medium | Must handle upstream errors per provider |

**Overall:** Medium complexity. The route handler is simple. The complexity is in
the 10+ provider adapters with different APIs. Start with openai (Group A), then
add gemini and elevenlabs (Group B), then the rest incrementally.

---

## Iterasi 1 Completion Report (2026-05-23)

### What shipped

| Component | File | Notes |
|---|---|---|
| TTS adapters module | `backend/app/services/tts_adapters.py` (NEW, ~200 lines) | `pcm_to_wav()` util + `tts_openai_compatible()` + `tts_hyperbolic()` + dispatch table `TTS_ADAPTERS`. **No default model/voice maps** — explicit values required from caller. |
| Model parser | `backend/app/services/proxy.py` (+50 lines) | `parse_tts_model()` — strict: requires both model and voice (raises `ValueError` if missing). Splits on **last** slash so multi-segment model IDs (`FunAudioLLM/CosyVoice2-0.5B/voice`) work. |
| Route handler | `backend/app/routers/v1_proxy.py` (+195 lines) | `POST /v1/audio/speech` — validation, alias resolution, adapter dispatch, DB connection lookup with priority order, fallback loop, binary + json response_format support, body-level `tts_model`/`voice`/`speed` overrides (model string can be bypassed by sending discrete fields), query-param `response_format` override |

### Design decision: No default model/voice (2026-05-23 revision)

Initial Iterasi 1 had `DEFAULT_TTS_MODELS` + `DEFAULT_VOICES` maps so e.g. `openai/alloy` would resolve to `(gpt-4o-mini-tts, alloy)`. **Removed** per user direction:

> "jangan pake default lah untuk semua media, sesuai model by fetch aja"

Rationale:
- Defaults hard-code 9Router's preferences (e.g. `gpt-4o-mini-tts` vs `tts-1` vs `tts-1-hd`) into the backend. Frontend already fetches model lists per provider via `/api/providers/{id}/models` — let the user pick from real data.
- Default voices are subjective and provider-specific (Rachel for ElevenLabs? Kore for Gemini?). Forcing a default is the wrong abstraction.
- Mirrors chat/embeddings convention: caller specifies the exact model, no aliasing back to a "default".

New contract:
- Model string MUST be `provider/model/voice` (model and voice both non-empty).
- Or: send `tts_model` + `voice` as discrete body fields (still required, just out-of-band).
- Missing either → 400 with an explicit error pointing to the fetch-from-provider workflow.

### Group A adapters wired
- `openai` — POST `{baseUrl}/audio/speech` body `{model, voice, input, response_format, speed?}`, binary response
- `siliconflow` — same as openai (OpenAI-compatible)
- `hyperbolic` — POST `{baseUrl}/audio/generation` body `{model, text, language, ...}`, JSON response with base64 `audio` field. `voice` param mapped to Hyperbolic's `language` field.

### Smoke tests passed (validation layer, 7/7)

| Test | Input | Expected | Actual |
|---|---|---|---|
| Missing model | `{"input": "Hi"}` | 400 | ✅ 400 `Missing required field: model` |
| Missing input | `{"model": "openai/alloy"}` | 400 | ✅ 400 `Missing required field: input` |
| No slash in model | `{"model": "openai", "input": "Hi"}` | 400 | ✅ 400 `Model must be in 'provider/model/voice' or 'provider/voice' format` |
| Provider+voice only (`openai/alloy`) | `{"model": "openai/alloy", "input": "Hi"}` | 400 | ✅ 400 `TTS model must be in 'provider/model/voice' format — both model and voice are required (no defaults)` |
| Trailing slash | `{"model": "openai/", "input": "Hi"}` | 400 | ✅ 400 (same error) |
| Multi-segment model | `{"model": "siliconflow/FunAudioLLM/CosyVoice2-0.5B/alex", "input": "Hi"}` | 503 (parses to model=`FunAudioLLM/CosyVoice2-0.5B`, voice=`alex`, then DB lookup fails) | ✅ 503 `No active connection for provider: siliconflow` |
| Full model+voice path | `{"model": "openai/gpt-4o-mini-tts/alloy", "input": "Hi"}` | 503 | ✅ 503 `No active connection for provider: openai` |
| Body override (discrete fields) | `{"model": "openai/whatever", "input": "Hi", "tts_model": "gpt-4o-mini-tts", "voice": "nova"}` | 503 (model string bypassed by body fields) | ✅ 503 `No active connection for provider: openai` |
| Unsupported provider | `{"model": "elevenlabs/eleven_multilingual_v2/Rachel", "input": "Hi"}` | 501 | ✅ 501 `TTS provider 'elevenlabs' is not yet supported. Iterasi 1 supports: hyperbolic, openai, siliconflow` |

### Deviations from plan

1. **Connection lookup uses `ProviderConnection` table directly**, not `resolve_model_to_targets()` (which is hard-coded to chat completions URL building). This is the right scope for TTS because:
   - TTS doesn't go through model aliasing (model string is already `provider/model/voice`)
   - TTS doesn't use combo rotation strategy (different lifecycle than chat)
   - Each adapter knows its own URL convention (some use `/audio/speech`, others `/audio/generation`, some have model in path)
2. **`tts_hyperbolic` is its own adapter** (not OpenAI-compat) — actual API is different enough (JSON response with base64, body uses `text` not `input`) to warrant its own adapter.
3. **Adapter signature uses kwargs-only** with `**_kwargs` catch-all so we can add params (e.g. `language` for gemini) without breaking other adapters.
4. **Body-level overrides allowed**: `tts_model`, `voice`, `response_format`, `speed` in body take precedence. When both `tts_model` and `voice` are present in body, the model string remainder is ignored entirely (still must start with `provider/` for routing).
5. **`json` response_format** wraps audio as base64 JSON — internal request still uses `mp3` to upstream, then re-encoded.
6. **No defaults** — see "Design decision" above.
7. **`parse_tts_model()` splits on LAST slash** to handle multi-segment model IDs like siliconflow's `FunAudioLLM/CosyVoice2-0.5B/voice_id`.

### Live audio tests deferred

No `openai`, `siliconflow`, or `hyperbolic` connections in DB at time of Iterasi 1 ship. User has nvidia connection but nvidia is Group B. To live-test Iterasi 1:

```bash
# Get JWT
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password": "123456"}' | jq -r '.access_token')

# Add an openai connection via dashboard (or API), then:
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini-tts/alloy", "input": "Hello from 9Router!"}' \
  --output test.mp3 -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```

### Files actually changed

| File | Change | Lines (net) |
|---|---|---|
| `backend/app/services/tts_adapters.py` | NEW | +200 |
| `backend/app/services/proxy.py` | `parse_tts_model()` at EOF (strict, no defaults) | +50 |
| `backend/app/routers/v1_proxy.py` | Route handler + imports | +195 |
| `docs/plans/v1-audio-speech.md` | Iteration tracking + report | +110 |
| `docs/porting-status.md` | TTS moved to "In Progress" | ~3 |
| `docs/plans/v1-proxy-endpoints.md` | Endpoint #2 status note | +5 |

**Total backend changes**: 3 files, ~445 lines added, no DB migrations, no frontend changes.

### Next iterasi (when user picks back up)

**Iterasi 2 targets**: Group B's 4 hardest adapters first (validate the unusual response shapes):
1. `tts_gemini` — PCM bytes from `inlineData.data` → `pcm_to_wav()` wrap (24kHz mono). Custom URL with `?key=` query param.
2. `tts_elevenlabs` — voice ID in URL path (`/text-to-speech/{voice_id}`), `xi-api-key` header.
3. `tts_minimax` — hex-encoded audio inside JSON `data.audio` field, complex `voice_setting` body.
4. `tts_openrouter` — SSE stream with `delta.audio.data` base64 chunks → concatenate → decode.

Each of these should be wired + smoke tested with a live API key before moving to the simpler Group B adapters (deepgram, nvidia, huggingface, inworld, cartesia, playht).

**Frontend note for Iterasi 2+**: TTS playground in MediaProviderDetailPage must fetch models via `/api/providers/{provider}/models?kind=tts` (or whatever the established endpoint is) and present model + voice as separate dropdowns — never hardcode a default. Backend will 400 if either is missing.

---

## Iterasi 2 Completion Report (2026-05-23)

### What shipped (Group B-1)

| Adapter | File location | Pattern | Output |
|---|---|---|---|
| `tts_gemini` | `tts_adapters.py` | generateContent with AUDIO modality; URL has model in path + `?key=` query param. Hardcoded URL (ignores base_url). PCM L16 24kHz mono → wrapped with `pcm_to_wav()`. | WAV (24kHz mono 16-bit) |
| `tts_elevenlabs` | `tts_adapters.py` | Voice ID embedded in URL path: `/v1/text-to-speech/{voice_id}`. Auth: `xi-api-key` header (NOT Bearer). Hardcoded URL. Min size check (1KB) catches empty/truncated responses. | Binary MP3 |
| `tts_minimax` | `tts_adapters.py` | T2A HTTP with hex-encoded audio in JSON response. Two-layer error check: HTTP status AND `base_resp.status_code`. Unique body shape (`voice_setting`, `audio_setting` objects). | MP3 (or whatever format requested) |
| `tts_openrouter` | `tts_adapters.py` | SSE stream via chat completions w/ `modalities=["text","audio"]`. Accumulates `delta.audio.data` base64 chunks across stream. Uses `httpx.AsyncClient.stream()` for proper async iteration. | WAV/MP3/FLAC/Opus per request |

**Bonus:** `minimax-cn` registered as alias for `tts_minimax` (same adapter, different base_url at connection level).

### Route handler changes

- **`_FIXED_URL_PROVIDERS` set** (gemini, elevenlabs, openrouter) — adapters with hardcoded endpoints skip the `base_url is empty` check that other adapters need. Without this, gemini connections (no base_url stored) would 500 before reaching the adapter.
- **`language` body field passthrough** — gemini's `tts_gemini` accepts optional `language` to bake into the prompt prefix ("Say in Spanish: hello"). Route handler now extracts `body.get("language")` and passes via `**extra` to all adapters (other adapters ignore via `**_kwargs`).

### Smoke tests (6/6 pass)

| Test | Input | Expected | Actual |
|---|---|---|---|
| Gemini live audio | `gemini/gemini-2.5-flash-preview-tts/Kore` + "Hello from 9Router Iterasi 2" | 200 WAV | ✅ **HTTP 200, 169530 bytes, RIFF/WAVE/PCM/16-bit/mono/24000Hz, Content-Type `audio/wav`** |
| ElevenLabs no conn | `elevenlabs/eleven_flash_v2_5/Rachel` | 503 | ✅ 503 `No active connection for provider: elevenlabs` |
| MiniMax no conn | `minimax/speech-2.5-hd-preview/English_expressive_narrator` | 503 | ✅ 503 `No active connection for provider: minimax` |
| OpenRouter pass-through | `openrouter/openai/gpt-4o-mini-tts/alloy` | Upstream error (we don't have a TTS-capable OR model handy) | ✅ HTTP 500 propagated from OpenRouter: `openai/gpt-4o-mini-tts is not a valid model ID` — adapter dispatched correctly, error is upstream |
| Still-unwired provider | `deepgram/aura/asteria-en` | 501 | ✅ 501 (updated message now lists 8 supported providers) |
| Still-unwired provider | `playht/PlayHT2/Bryan` | 501 | ✅ 501 |

### Files actually changed

| File | Change | Lines (net) |
|---|---|---|
| `backend/app/services/tts_adapters.py` | +4 Group B adapters + `_build_gemini_prompt()` helper + dispatch table extension | +290 |
| `backend/app/routers/v1_proxy.py` | `_FIXED_URL_PROVIDERS` set + `language` passthrough | +12 |
| `docs/plans/v1-audio-speech.md` | Iterasi 2 report | +60 (this section) |
| `docs/porting-status.md` | Status update (Iterasi 2) | ~3 |

**Total Iterasi 2 changes**: 2 code files, ~302 lines added, no DB migrations, no frontend changes.

### Live test verification

```
$ curl -s -X POST http://localhost:9000/v1/audio/speech \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"model": "gemini/gemini-2.5-flash-preview-tts/Kore", "input": "Hello from 9Router Iterasi 2"}' \
    --output /tmp/gemini_test.wav -w 'HTTP %{http_code} | Size: %{size_download} bytes | Content-Type: %{content_type}\n'

HTTP 200 | Size: 169530 bytes | Content-Type: audio/wav

$ file /tmp/gemini_test.wav
/tmp/gemini_test.wav: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 24000 Hz
```

WAV header matches expected spec exactly (RIFF + WAVE + PCM + 16-bit + mono + 24000 Hz). Audio bytes decoded from Gemini's base64 inlineData wrapped by `pcm_to_wav()` produced a valid playable file.

### Deviations from plan / surprises

1. **No defaults rule applied to OpenRouter** — original 9router OpenRouter adapter defaulted to `openai/gpt-4o-mini-tts` and `alloy`. We removed these defaults per user direction. Caller must explicitly pick a TTS-capable OpenRouter model.
2. **Parser ambiguity for OpenRouter** — model strings like `openrouter/openai/gpt-4o-mini-tts/alloy` are parsed as `model="openai/gpt-4o-mini-tts", voice="alloy"` via `rsplit("/", 1)` in `parse_tts_model()`. This works because the parser splits on the LAST slash. No special-casing needed.
3. **Gemini just worked** — first cold path through the route handler hit a real connection and returned valid audio with no debugging needed. The kwargs-only adapter signature + `**_kwargs` ignore-extras pattern paid off.
4. **`extra` dict propagation** — for `language` body field. Future Group B-2 adapters can use the same mechanism for adapter-specific kwargs (e.g. deepgram has `encoding`, cartesia has `language` + `emotion`).
5. **OpenRouter 500 in test 4 is not a bug** — the request reached OpenRouter successfully and OpenRouter rejected `openai/gpt-4o-mini-tts` as an unknown model. To live-test, lo perlu pakai TTS model yang OpenRouter actually expose (check `https://openrouter.ai/models?modality=audio`).

### Next iterasi (when user picks back up)

**Iterasi 3 targets**: Group B-2 simple binary providers (all relatively easy — body shapes are simple, responses are just bytes):
1. `tts_nvidia` — POST `{base_url}` body `{input: {text}, voice, model}`, binary WAV. URL is fully-qualified (no path building).
2. `tts_deepgram` — POST `{base_url}/speak?model={model}`, body `{text}`, `Token` auth (NOT Bearer), binary response. Model encoded in query param, not body.
3. `tts_huggingface` — POST `{base_url}/{model_id}` body `{inputs: text}`, binary. Path includes model ID — must sanitize against `..`.
4. `tts_inworld` — POST `{base_url}/tts/v1/voice` body `{text, voice}`, binary WAV.
5. `tts_cartesia` — POST `{base_url}/tts/bytes` body `{model_id, transcript, voice: {mode, id}, output_format}`. Has `Cartesia-Version` header requirement.
6. `tts_playht` — POST `{base_url}/api/v2/tts/stream` with `X-USER-ID` header. Returns stream of binary chunks.

Since user has nvidia connection, Iterasi 3 should start with `tts_nvidia` for an immediate live audio verification.

### Iterasi 3 — Done (2026-05-23)

All 6 Group B-2 adapters implemented in `backend/app/services/tts_adapters.py` and wired into `TTS_ADAPTERS` dispatch table. Final adapter count: **14** (3 Group A + 5 Group B-1 + 6 Group B-2).

**Implementation notes per provider:**

1. **deepgram** — `voice` (e.g. `aura-asteria-en`) goes as `?model=` query param on the base URL (`https://api.deepgram.com/v1/speak`). `Token` auth prefix, NOT `Bearer`. Falls back to `tts_model` if `voice` empty. Body is just `{text}`. Returns binary MP3.
2. **nvidia** — `base_url` is the full endpoint (`https://integrate.api.nvidia.com/v1/audio/speech`), no path building. Body: `{input: {text}, voice, model}`. `Bearer` auth. Validates non-empty voice. Returns binary WAV.
3. **huggingface** — Path includes model ID: `{base_url}/{tts_model}` (e.g. `https://api-inference.huggingface.co/models/facebook/mms-tts-eng`). Rejects `..` traversal + empty model. `voice` is ignored (HF TTS models are voice-fixed). Body: `{inputs: text}`. Returns binary audio.
4. **inworld** — `Basic` auth prefix (caller must pre-encode the base64 `userId:secret`). Defaults: `voiceId="Alex"`, `modelId="inworld-tts-1.5-mini"`. Response is JSON `{audioContent: <base64>}` — adapter decodes to MP3 bytes.
5. **cartesia** — `X-API-Key` header (not Bearer) + required `Cartesia-Version: 2024-06-10` header. Body: `{model_id, transcript, output_format: {container, bit_rate, sample_rate}}`. Voice (when given) wrapped as `{mode: "id", id: voice}`. Defaults: mp3 @ 128kbps / 44.1kHz. Returns binary MP3.
6. **playht** — `api_key` is `"userId:apiKey"` colon-joined; adapter splits on partition. Sends both `X-USER-ID` header AND `Authorization: Bearer <key>`. Validates both halves non-empty. `voice` is typically an S3 manifest URL; validated non-empty. Body: `{text, voice, voice_engine, output_format: "mp3", speed: 1}`.

**Verification — 20 smoke checks pass (`/tmp/smoke_b2.py`):**
- 6 happy-path: URL shape, auth header style, body shape, response decoding per provider
- 12 validation-rejection: empty voice/model, path traversal (HF `..`), malformed PlayHT keys (`""`, `"onlyuser"`, `":onlykey"`, `"user:"`), empty voice (NVIDIA, PlayHT), empty model (Cartesia, HF), empty voice+model (Deepgram)
- 2 default-fallback: Inworld voiceId/modelId defaults, Cartesia omits `voice` key when empty
- Bonus: NVIDIA non-2xx propagation (401 → `ValueError` w/ status code)

**Live-testing checklist (for when API keys are available):**
- nvidia: `POST /v1/audio/speech {"model":"nvidia/magpie-tts-multilingual/English-US.Female-1","input":"hello"}`
- deepgram: `POST /v1/audio/speech {"model":"deepgram/aura-asteria-en/aura-asteria-en","input":"hi"}` (voice doubles as model)
- huggingface: `POST /v1/audio/speech {"model":"huggingface/facebook/mms-tts-eng/_","input":"hi"}` — needs 4-segment parse or `tts_model`/`voice` body fields
- inworld: `POST /v1/audio/speech {"model":"inworld/inworld-tts-1.5-mini/Alex","input":"hi"}`
- cartesia: `POST /v1/audio/speech {"model":"cartesia/sonic-2/<voice-id>","input":"hi"}`
- playht: `POST /v1/audio/speech {"model":"playht/PlayDialog/s3://...manifest.json","input":"hi"}`

**Caveats discovered:**
- `parse_tts_model` expects exactly two segments (`model/voice`). HuggingFace model IDs containing `/` (e.g. `facebook/mms-tts-eng`) may break this — workaround is to use body-level `tts_model` + `voice` fields instead of cramming everything into the `model` string. Worth flagging in Iterasi 4 frontend wiring.
- Cartesia `Cartesia-Version` is REQUIRED — without it API returns 400. Locked to `2024-06-10` (matches JS reference); revisit if API version drifts.
- PlayHT auth format `userId:apiKey` is unique among providers. Frontend's API-key save form needs to make this explicit, otherwise users will save just the key half and the adapter will reject it with a clear error.

**Frontend wiring for Iterasi 4** (after backend complete): TTS playground in `MediaProviderDetailPage.jsx` must:
- Use `/api/providers/{id}/models?kind=tts` to populate model dropdown
- Add separate voice dropdown sourced from `/api/media-providers/tts/{provider}/voices` (or equivalent)
- Send `provider/{model}/{voice}` to `/v1/audio/speech`
- Display returned audio in a playable `<audio>` element with download button
