# Plan: GET /v1/audio/voices

**Status:** 🟢 Phase 1-4 complete & live-verified for 4 providers (gemini, deepgram, edge-tts, local-device-empty); 4 paid providers deferred pending credentials (elevenlabs, inworld, minimax, minimax-cn).
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/audio/voices/route.js`  
**Estimated effort:** Medium — not a proxy endpoint but a voice catalog aggregator with 8 provider-specific upstream APIs.

---

## What This Does

Returns a list of available TTS voices for a given provider, formatted as an
OpenAI-compatible voice list. Each voice includes a `model` field pre-formatted
for use with `POST /v1/audio/speech` (format: `{alias}/{voice_id}`).

```
Client → GET /v1/audio/voices?provider=elevenlabs&lang=en
           ↓
       fetch voices from provider's upstream API
           ↓
       normalize to OpenAI voice list format
           ↓
       return { object: "list", data: [{ id, name, lang, gender, model }] }
```

**This is NOT a proxy endpoint.** It does not forward requests to an upstream
provider. Instead, it queries each provider's voice catalog API and normalizes
the response into a unified format.

---

## Key Difference From Other v1 Endpoints

1. **GET request** — not POST. No request body.
2. **Provider-specific upstream APIs** — each provider has a completely different
   voice listing API (different URLs, auth methods, response shapes).
3. **Depends on TTS voices sub-endpoints** — the original delegates to internal
   `/api/media-providers/tts/{provider}/voices` endpoints which are also not
   yet ported to FastAPI.
4. **Two-layer architecture** — `/v1/audio/voices` is a thin wrapper that calls
   internal voice-fetching endpoints, maps the response to OpenAI format.
5. **No DB lookup needed** — voices come from upstream provider APIs, not from
   the provider_connections table (except for API key retrieval).

---

## Architecture

```
GET /v1/audio/voices?provider=elevenlabs&lang=en
    │
    ├── fetch from internal /api/media-providers/tts/elevenlabs/voices
    │   └── upstream: GET https://api.elevenlabs.io/v1/voices
    │
    ├── normalize response to OpenAI format
    │   └── { object: "list", data: [{ id, name, lang, gender, model: "el/{voice_id}" }] }
    │
    └── return to client
```

The original has a two-layer system:

**Layer 1:** `/v1/audio/voices` — public OpenAI-compatible endpoint  
**Layer 2:** `/api/media-providers/tts/{provider}/voices` — internal provider-specific endpoints

Both layers need to be ported. The recommended approach for FastAPI is to
implement the voice-fetching logic directly in the `/v1/audio/voices` handler
(rather than creating separate internal endpoints), since the FastAPI backend
doesn't need the intermediate internal API layer that Next.js required.

---

## Supported Providers

| Provider      | Alias | Upstream Voice API                                    | Auth              | Notes                                     |
|---------------|-------|------------------------------------------------------|-------------------|-------------------------------------------|
| elevenlabs    | el    | GET https://api.elevenlabs.io/v1/voices              | xi-api-key header | Returns full voice objects with labels     |
| deepgram      | dg    | GET https://api.deepgram.com/v1/models               | Token header      | Returns TTS models, each = one voice       |
| inworld       | iw    | GET https://api.inworld.ai/tts/v1/voices             | Basic auth        | Returns voices with language arrays        |
| edge-tts      | edge-tts | GET https://speech.platform.bing.com/.../voices/list | None (no auth)  | Microsoft Edge TTS voices, cached 24h      |
| local-device  | local-device | Local OS voices                               | None (no auth)  | System TTS voices, varies by OS            |
| minimax       | minimax | POST https://api.minimax.io/v1/get_voice           | Bearer token      | Returns system_voice, voice_cloning groups |
| minimax-cn    | minimax-cn | POST https://api.minimaxi.com/v1/get_voice       | Bearer token      | China endpoint, same format                |
| gemini        | gemini | Hardcoded list                                       | None (no API)     | 30 prebuilt voices, no list API            |

---

## Request / Response Format

**Request:**
```
GET /v1/audio/voices?provider={provider_id}[&lang={lang_code}]
Authorization: Bearer <jwt_or_api_key>
```

- `provider` (required) — provider ID (elevenlabs, deepgram, inworld, edge-tts, local-device, minimax, minimax-cn, gemini)
- `lang` (optional) — ISO 639-1 language code to filter voices

**Response (OpenAI-compatible):**
```json
{
  "object": "list",
  "data": [
    {
      "id": "Rachel",
      "name": "Rachel",
      "lang": "en",
      "gender": "female",
      "model": "el/Rachel"
    },
    {
      "id": "Domi",
      "name": "Domi",
      "lang": "en",
      "gender": "female",
      "model": "el/Domi"
    }
  ]
}
```

The `model` field is pre-formatted for direct use with `POST /v1/audio/speech`:
- `el/Rachel` → use as model in `POST /v1/audio/speech` with provider=elevenlabs
- `dg/aura-asteria-en` → use with provider=deepgram
- `edge-tts/en-US-AriaNeural` → use with provider=edge-tts

**Error response:**
```json
{
  "error": {
    "message": "provider must be one of: elevenlabs, deepgram, inworld, edge-tts, local-device, minimax, gemini",
    "type": "invalid_request_error"
  }
}
```

---

## Phase 1 — Backend: Voice Fetcher Adapters

**New file:** `backend/app/services/voice_fetchers.py`

One function per provider that returns a list of normalized voice objects.

### 1.1 ElevenLabs Voice Fetcher

```python
async def fetch_elevenlabs_voices(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    """Fetch ElevenLabs voices via REST API."""
    resp = await client.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
    )
    resp.raise_for_status()
    
    voices = []
    for v in resp.json().get("voices", []):
        voices.append({
            "id": v["voice_id"],
            "name": v["name"],
            "lang": v.get("labels", {}).get("language", "en"),
            "gender": v.get("labels", {}).get("gender", ""),
        })
    return voices
```

### 1.2 Deepgram Voice Fetcher

```python
async def fetch_deepgram_voices(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    """Fetch Deepgram TTS models (each model = one voice)."""
    resp = await client.get(
        "https://api.deepgram.com/v1/models",
        headers={"Authorization": f"Token {api_key}"},
    )
    resp.raise_for_status()
    
    voices = []
    for m in resp.json().get("tts", []):
        langs = m.get("languages", ["en"])
        voice_id = m.get("canonical_name") or m.get("name", "")
        gender = ""
        for tag in m.get("metadata", {}).get("tags", []):
            if tag in ("masculine", "feminine"):
                gender = tag
                break
        
        for lang in langs:
            voices.append({
                "id": voice_id,
                "name": m.get("name", voice_id),
                "lang": lang,
                "gender": gender,
            })
    return voices
```

### 1.3 Inworld Voice Fetcher

```python
async def fetch_inworld_voices(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    """Fetch Inworld TTS voices."""
    resp = await client.get(
        "https://api.inworld.ai/tts/v1/voices",
        headers={"Authorization": f"Basic {api_key}"},
    )
    resp.raise_for_status()
    
    voices = []
    for v in resp.json().get("voices", []):
        langs = v.get("languages", ["en"])
        voice_id = v.get("voiceId", "")
        for lang in langs:
            voices.append({
                "id": voice_id,
                "name": v.get("displayName", voice_id),
                "lang": lang,
                "gender": v.get("gender", ""),
            })
    return voices
```

### 1.4 Edge TTS Voice Fetcher

```python
async def fetch_edge_tts_voices(client: httpx.AsyncClient) -> list[dict]:
    """Fetch Microsoft Edge TTS voices (no auth required)."""
    resp = await client.get(
        "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list"
        "?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4",
    )
    resp.raise_for_status()
    
    voices = []
    for v in resp.json():
        locale = v.get("Locale", "")
        lang = locale.split("-")[0] if locale else "en"
        voices.append({
            "id": v.get("ShortName", ""),
            "name": (v.get("FriendlyName", v.get("ShortName", ""))
                     .replace("Microsoft ", "")
                     .replace(" Online (Natural) - ", " (")),
            "lang": lang,
            "gender": v.get("Gender", "").lower(),
        })
    return voices
```

### 1.5 MiniMax Voice Fetcher

```python
async def fetch_minimax_voices(
    client: httpx.AsyncClient,
    api_key: str,
    provider: str = "minimax",
) -> list[dict]:
    """Fetch MiniMax voices via POST /v1/get_voice."""
    endpoints = {
        "minimax": "https://api.minimax.io/v1/get_voice",
        "minimax-cn": "https://api.minimaxi.com/v1/get_voice",
    }
    
    resp = await client.post(
        endpoints[provider],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"voice_type": "all"},
    )
    resp.raise_for_status()
    data = resp.json()
    
    # Check MiniMax-specific error format
    base_resp = data.get("base_resp") or data.get("baseResp", {})
    status_code = base_resp.get("status_code") or base_resp.get("statusCode", 0)
    if status_code != 0:
        raise Exception(base_resp.get("status_msg") or base_resp.get("statusMsg", "MiniMax error"))
    
    voices = []
    for group_key, group_label in [
        ("system_voice", "System"),
        ("voice_cloning", "Cloned"),
        ("voice_generation", "Generated"),
    ]:
        for item in data.get(group_key, []):
            voice_id = item.get("voice_id") or item.get("voiceId", "")
            voice_name = item.get("voice_name") or item.get("voiceName", voice_id)
            
            # Infer language from voice_id prefix (e.g. "English_..." → "English")
            lang = "Custom"
            if group_key == "system_voice" and "_" in voice_id:
                lang = voice_id.split("_")[0]
            
            voices.append({
                "id": voice_id,
                "name": f"{voice_name} · {group_label}" if group_key != "system_voice" else voice_name,
                "lang": lang,
                "gender": "",
            })
    return voices
```

### 1.6 Gemini Voice Fetcher

Gemini has no voice list API — returns a hardcoded list of 30 prebuilt voices.

```python
GEMINI_VOICES = [
    {"id": "Zephyr", "name": "Zephyr", "lang": "en", "gender": "Female"},
    {"id": "Puck", "name": "Puck", "lang": "en", "gender": "Male"},
    {"id": "Charon", "name": "Charon", "lang": "en", "gender": "Male"},
    {"id": "Kore", "name": "Kore", "lang": "en", "gender": "Female"},
    {"id": "Fenrir", "name": "Fenrir", "lang": "en", "gender": "Male"},
    {"id": "Leda", "name": "Leda", "lang": "en", "gender": "Female"},
    {"id": "Orus", "name": "Orus", "lang": "en", "gender": "Male"},
    {"id": "Aoede", "name": "Aoede", "lang": "en", "gender": "Female"},
    {"id": "Callirrhoe", "name": "Callirrhoe", "lang": "en", "gender": "Female"},
    {"id": "Autonoe", "name": "Autonoe", "lang": "en", "gender": "Female"},
    {"id": "Enceladus", "name": "Enceladus", "lang": "en", "gender": "Male"},
    {"id": "Iapetus", "name": "Iapetus", "lang": "en", "gender": "Male"},
    {"id": "Umbriel", "name": "Umbriel", "lang": "en", "gender": "Male"},
    {"id": "Algieba", "name": "Algieba", "lang": "en", "gender": "Male"},
    {"id": "Despina", "name": "Despina", "lang": "en", "gender": "Female"},
    {"id": "Erinome", "name": "Erinome", "lang": "en", "gender": "Female"},
    {"id": "Algenib", "name": "Algenib", "lang": "en", "gender": "Male"},
    {"id": "Rasalgethi", "name": "Rasalgethi", "lang": "en", "gender": "Male"},
    {"id": "Laomedeia", "name": "Laomedeia", "lang": "en", "gender": "Female"},
    {"id": "Achernar", "name": "Achernar", "lang": "en", "gender": "Female"},
    {"id": "Alnilam", "name": "Alnilam", "lang": "en", "gender": "Male"},
    {"id": "Schedar", "name": "Schedar", "lang": "en", "gender": "Male"},
    {"id": "Gacrux", "name": "Gacrux", "lang": "en", "gender": "Female"},
    {"id": "Pulcherrima", "name": "Pulcherrima", "lang": "en", "gender": "Female"},
    {"id": "Achird", "name": "Achird", "lang": "en", "gender": "Male"},
    {"id": "Zubenelgenubi", "name": "Zubenelgenubi", "lang": "en", "gender": "Male"},
    {"id": "Vindemiatrix", "name": "Vindemiatrix", "lang": "en", "gender": "Female"},
    {"id": "Sadachbia", "name": "Sadachbia", "lang": "en", "gender": "Male"},
    {"id": "Sadaltager", "name": "Sadaltager", "lang": "en", "gender": "Male"},
    {"id": "Sulafat", "name": "Sulafat", "lang": "en", "gender": "Female"},
]

async def fetch_gemini_voices() -> list[dict]:
    """Return hardcoded Gemini TTS voices (no list API available)."""
    return [dict(v) for v in GEMINI_VOICES]
```

### 1.7 Local Device Voice Fetcher

```python
async def fetch_local_device_voices() -> list[dict]:
    """Fetch local OS TTS voices (platform-dependent)."""
    import platform
    import subprocess
    
    voices = []
    system = platform.system()
    
    if system == "Linux":
        try:
            result = subprocess.run(
                ["espeak", "--voices"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n")[1:]:  # skip header
                parts = line.split()
                if len(parts) >= 4:
                    voices.append({
                        "id": parts[3],
                        "name": parts[3],
                        "lang": parts[1].split("-")[0] if len(parts) > 1 else "en",
                        "gender": "male" if "M" in parts[0] else "female",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if parts:
                    voices.append({
                        "id": parts[0],
                        "name": parts[0],
                        "lang": parts[1].split("_")[0] if len(parts) > 1 else "en",
                        "gender": "",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    
    return voices
```

---

## Phase 2 — Backend: Dispatch & Caching

### 2.1 Provider Dispatch Map

```python
VOICE_FETCHER_PROVIDERS = {
    "elevenlabs",
    "deepgram",
    "inworld",
    "edge-tts",
    "local-device",
    "minimax",
    "minimax-cn",
    "gemini",
}

async def fetch_voices_for_provider(
    client: httpx.AsyncClient,
    provider: str,
    api_key: str = "",
    lang: str = None,
) -> list[dict]:
    """Dispatch to the correct voice fetcher for a provider."""
    if provider == "elevenlabs":
        voices = await fetch_elevenlabs_voices(client, api_key)
    elif provider == "deepgram":
        voices = await fetch_deepgram_voices(client, api_key)
    elif provider == "inworld":
        voices = await fetch_inworld_voices(client, api_key)
    elif provider == "edge-tts":
        voices = await fetch_edge_tts_voices(client)
    elif provider == "local-device":
        voices = await fetch_local_device_voices()
    elif provider in ("minimax", "minimax-cn"):
        voices = await fetch_minimax_voices(client, api_key, provider)
    elif provider == "gemini":
        voices = await fetch_gemini_voices()
    else:
        raise ValueError(f"Provider '{provider}' does not support voice listing")
    
    # Apply language filter
    if lang:
        voices = [v for v in voices if v.get("lang") == lang]
    
    return voices
```

### 2.2 In-Memory Cache

Voice lists don't change frequently. Cache for 1 hour to avoid hammering
upstream APIs:

```python
import time

_voice_cache: dict[str, tuple[float, list]] = {}
VOICE_CACHE_TTL = 3600  # 1 hour

async def fetch_voices_cached(
    client: httpx.AsyncClient,
    provider: str,
    api_key: str = "",
    lang: str = None,
) -> list[dict]:
    """Fetch voices with in-memory cache (1h TTL)."""
    cache_key = f"{provider}:{lang or 'all'}"
    now = time.time()
    
    if cache_key in _voice_cache:
        cached_time, cached_voices = _voice_cache[cache_key]
        if now - cached_time < VOICE_CACHE_TTL:
            return cached_voices
    
    voices = await fetch_voices_for_provider(client, provider, api_key, lang)
    _voice_cache[cache_key] = (now, voices)
    return voices
```

---

## Phase 3 — Backend: Get API Key From DB

Most providers need an API key from the provider_connections table:

```python
async def get_provider_api_key(db: AsyncSession, provider: str) -> str | None:
    """Get the first active API key for a provider from DB."""
    result = await db.execute(
        select(ProviderConnection)
        .where(
            ProviderConnection.provider == provider,
            ProviderConnection.is_active == True,
        )
        .order_by(ProviderConnection.priority)
    )
    conn = result.scalars().first()
    if not conn:
        return None
    
    data = json.loads(conn.data) if conn.data else {}
    return data.get("apiKey") or data.get("accessToken")
```

---

## Phase 4 — Backend: Add `/v1/audio/voices` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.get("/audio/voices")
async def audio_voices(
    request: Request,
    provider: str = Query(..., description="TTS provider ID"),
    lang: str = Query(None, description="Filter by language code (ISO 639-1)"),
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """List available TTS voices for a provider (OpenAI-compatible format)."""
    from app.services.voice_fetchers import VOICE_FETCHER_PROVIDERS, fetch_voices_cached
    from app.services.proxy import ID_TO_ALIAS
    
    if provider not in VOICE_FETCHER_PROVIDERS:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": f"provider must be one of: {', '.join(sorted(VOICE_FETCHER_PROVIDERS))}",
                    "type": "invalid_request_error",
                }
            },
        )
    
    # Get API key from DB (not needed for edge-tts, local-device, gemini)
    api_key = ""
    if provider not in ("edge-tts", "local-device", "gemini"):
        api_key = await get_provider_api_key(db, provider) or ""
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": f"No {provider} connection found"}},
            )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            voices = await fetch_voices_cached(client, provider, api_key, lang)
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": str(e), "type": "server_error"}},
        )
    
    # Build provider alias for model field
    alias = ID_TO_ALIAS.get(provider, provider)
    
    # Normalize to OpenAI voice list format
    data_out = [
        {
            "id": v["id"],
            "name": v["name"],
            "lang": v.get("lang", ""),
            "gender": v.get("gender", ""),
            "model": f"{alias}/{v['id']}",
        }
        for v in voices
    ]
    
    return JSONResponse(content={"object": "list", "data": data_out})
```

---

## Phase 5 — Frontend: No Changes Required (for this endpoint)

The `/v1/audio/voices` endpoint is a pure API endpoint. **No UI changes are
required to ship this endpoint** — it is consumed by CLI tools and external
OpenAI-compatible clients.

The MediaProvidersPage already shows TTS providers via separate mechanisms.
Wiring a voice picker on MediaProvidersPage to this new endpoint is an
**optional enhancement**, tracked as future work below — it is explicitly
**out of scope** for this plan and does not block completion.

---

## Phase 6 — Testing

### 6.1 Manual curl tests

Get token first:
```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — Edge TTS voices (no auth, happy path):**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=edge-tts" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length), sample: .data[0]}'
```
Expected: `count > 100`, sample voice has `id`, `name`, `lang`, `gender`, `model`.

**Test 2 — Edge TTS with language filter:**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=edge-tts&lang=en" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length)}'
```
Expected: Only English voices returned.

**Test 3 — ElevenLabs voices (requires API key):**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=elevenlabs" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length), sample: .data[0]}'
```
Expected: `count > 0`, `model` starts with `el/`.

**Test 4 — Deepgram voices:**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=deepgram" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length), sample: .data[0]}'
```
Expected: `count > 0`, `model` starts with `dg/`.

**Test 5 — Gemini voices (hardcoded, no API key needed):**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=gemini" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: (.data | length), sample: .data[0]}'
```
Expected: `count: 30`, `model` starts with `gemini/`.

**Test 6 — Invalid provider (400):**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=nonexistent" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `400` with `"provider must be one of: ..."`.

**Test 7 — Missing provider param (422):**
```bash
curl -s "http://localhost:9000/v1/audio/voices" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `422` with validation error for missing `provider` query param.

**Test 8 — No connection for provider (400):**
```bash
curl -s "http://localhost:9000/v1/audio/voices?provider=inworld" \
  -H "Authorization: Bearer $TOKEN" | jq .
```
Expected: `400` with `"No inworld connection found"` (if no inworld connection configured).

**Test 9 — Verify model field works with TTS endpoint:**
```bash
# First get a voice
VOICE_MODEL=$(curl -s "http://localhost:9000/v1/audio/voices?provider=edge-tts&lang=en" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.data[0].model')

# Then use it with TTS
curl -s -X POST http://localhost:9000/v1/audio/speech \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$VOICE_MODEL\", \"input\": \"Hello from 9Router!\"}" \
  --output test_voice.mp3 -w "HTTP %{http_code} Size: %{size_download} bytes\n"
```
Expected: HTTP 200, playable MP3 file.

**Test 10 — Cache verification (second request should be faster):**
```bash
# First request (cold)
time curl -s "http://localhost:9000/v1/audio/voices?provider=edge-tts" \
  -H "Authorization: Bearer $TOKEN" > /dev/null

# Second request (cached)
time curl -s "http://localhost:9000/v1/audio/voices?provider=edge-tts" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
```
Expected: Second request significantly faster (< 100ms).

### 6.2 Verify in running app

1. Open http://localhost:5173
2. Navigate to Media Providers → Text to Speech
3. Confirm TTS providers still display correctly — no regressions
4. Check Console Log page — curl requests should appear

### 6.3 Regression check

```bash
# Chat completions
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 7 — Report

1. **`docs/porting-status.md`** — Move `GET /v1/audio/voices` from "Not Yet Ported" to "Fully Ported".

2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 4 as done:
   change `GET /v1/audio/voices` status to ✅.

3. **`docs/plans/v1-audio-voices.md`** (this file) — Update status at top
   from `Not started` to `Done`, add completion date and notes.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Local device voices | Platform-dependent (Linux: espeak, macOS: say). May return empty on Docker containers without TTS installed. |
| Edge TTS voices list | Fetched from Microsoft Bing endpoint. If Microsoft changes the endpoint, this breaks. Cache mitigates rate limiting. |
| Gemini voices | Hardcoded list of 30 voices. If Google adds new voices, they won't appear until the code is updated. |
| MiniMax voice groups | Includes system_voice, voice_cloning, voice_generation. Cloned/generated voices require the user to have created them in MiniMax dashboard. |
| Deepgram voice deduplication | Same voice may appear for multiple languages. The original deduplicates by voice ID within each language group. |
| ElevenLabs verified_languages | A voice can support multiple languages. The original adds it to each language group. The simplified version here only uses primary language. |
| Cache invalidation | Cache TTL is 1 hour. No manual cache-bust endpoint. If user adds a new cloned voice in MiniMax, it won't appear for up to 1 hour. |
| `local-device` in Docker | Docker containers typically don't have OS TTS engines. This provider will return empty results. |
| AWS Polly voices | Not in the original's `/v1/audio/voices` supported list. Can be added later. |
| PlayHT voices | Not in the original's supported list. Can be added later. |
| Cartesia voices | Not in the original's supported list. Can be added later. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/voice_fetchers.py` | NEW — Voice fetcher adapters per provider, cache, DB helper |
| `backend/app/routers/v1_proxy.py` | Add `GET /v1/audio/voices` handler |
| `docs/porting-status.md` | Move voices endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 4 done |
| `docs/plans/v1-audio-voices.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Low | Simple GET with query params |
| ElevenLabs adapter | Low | Standard REST API, JSON response |
| Deepgram adapter | Low | REST API, normalize model list to voice format |
| Inworld adapter | Low | REST API, voices with language arrays |
| Edge TTS adapter | Low | No-auth public endpoint, large voice list |
| MiniMax adapter | Medium | POST with voice groups, hex parsing not needed (only for TTS), MiniMax-specific error format |
| Gemini adapter | Trivial | Hardcoded list, no API call |
| Local device adapter | Medium | Platform-dependent subprocess calls |
| Caching | Low | Simple in-memory dict with TTL |
| Model field normalization | Low | Prefix with provider alias |

**Overall:** Low-medium complexity. Most adapters are straightforward REST calls
with response normalization. The main challenge is getting the response shape
right for each provider and ensuring the `model` field is correctly formatted
for use with `/v1/audio/speech`.

**Recommended implementation order:**
1. Gemini (trivial — hardcoded list)
2. Edge TTS (no auth, public endpoint)
3. ElevenLabs (simple REST, well-documented API)
4. Deepgram (simple REST)
5. Inworld (simple REST)
6. MiniMax (POST with groups, more complex)
7. Local device (platform-dependent, lowest priority)

---

## Implementation Log

**Date:** 2026-05-23
**Approach:** Incremental — implemented Phase 1-4 for all 8 providers, live-verified the 4 testable ones, deferred 4 paid providers pending credentials.

**Files created/modified:**
- `backend/app/services/voice_fetchers.py` (NEW) — 7 adapter functions + dispatch + 1h cache
- `backend/app/routers/v1_proxy.py` — added `GET /v1/audio/voices` route (Phase 4)

**Implementation notes:**
- `voice_fetchers.py` uses `asyncio.to_thread` for subprocess calls in local-device adapter (plan spec'd `subprocess.run` synchronously, but that would block the event loop).
- `edge-tts` fetcher guards against non-list JSON responses (defensive against MS endpoint changes).
- `minimax` adapter supports both camelCase and snake_case error envelopes.
- Auth pattern uses existing `validate_api_key` dependency like other v1 endpoints.
- `is_no_key_provider()` helper centralizes the set `{"edge-tts", "local-device", "gemini"}`.

**Known limitations:**
- `local-device` in Docker returns 0 voices (no `espeak` installed). Acceptable for a server deployment.
- `gemini` voices are all `lang: en` — if/when Google adds non-English prebuilt voices, the hardcoded list needs a refresh.
- `edge-tts` relies on MS's `trustedclienttoken` which may rotate; the token in plan works today (2026-05-23).

---

## Iterasi 2 Live Verification

Same test approach as `v1-audio-transcriptions.md` — hit endpoint via curl from outside container.

| Provider | Auth | Status | Voices returned | Sample `model` |
|---|---|---|---|---|
| gemini | hardcoded (no key) | ✅ 200 | 30 | `gemini/Zephyr` |
| deepgram | Token header (DB key) | ✅ 200 | 204 | `deepgram/aura-2-agathe-fr` |
| edge-tts | no key | ✅ 200 | 322 | `edge-tts/af-ZA-AdriNeural` |
| local-device | no key (Docker Linux) | ✅ 200 | 0 | — |
| elevenlabs | — | ⏸ 400 | — | No key in DB (paid, deferred) |
| inworld | — | ⏸ 400 | — | No key in DB (paid, deferred) |
| minimax | — | ⏸ 400 | — | No key in DB (paid, deferred) |
| minimax-cn | — | ⏸ 400 | — | No key in DB (paid, deferred) |

**Error-path checks:**
| Scenario | HTTP | Response |
|---|---|---|
| invalid provider (`provider=foo`) | 400 | `provider must be one of: deepgram, edge-tts, ...` |
| missing provider param | 422 | FastAPI auto-validation error |
| elevenlabs no key | 400 | `No elevenlabs connection found` |
| gemini `lang=fr` filter | 200 | 0 voices (hardcoded list is all en) |
| gemini `lang=en` filter | 200 | 30 voices |

**Caching:** First call fetches upstream, subsequent calls within 1h served from `_voice_cache`. Verified by rapid re-call — response time drops from ~400ms (deepgram) to <5ms.

---

## Iterasi 2 Pending Work

- [ ] Verify ElevenLabs (needs paid key in DB)
- [ ] Verify Inworld (needs paid key in DB)
- [ ] Verify MiniMax / MiniMax-CN (needs paid key in DB)
- [ ] (Optional) Install `espeak` in Docker backend image to enable `local-device` voice listing in production
- [ ] (Optional, out of scope) Frontend enhancement — wire `MediaProvidersPage` voice picker to this endpoint. Not part of this plan; TTS page already functions without it.
