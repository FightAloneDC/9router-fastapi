# Plan: POST /v1/audio/transcriptions (STT)

**Status:** 🚧 Iterasi 2 In Progress — 4/8 providers live-verified (Groq Whisper ✅, Gemini STT ✅, Deepgram ✅, AssemblyAI ✅), 1 removed by design (NVIDIA — no REST endpoint), 3 pending DB credentials (OpenAI Whisper, HuggingFace, Azure)
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`
**Original source:** `~/dev/9router/src/app/api/v1/audio/transcriptions/route.js` → `src/sse/handlers/stt.js` → `open-sse/handlers/sttCore.js`
**Implementation deviations from original plan:** see "Implementation Notes" section below.

---

## What This Does

Adds an OpenAI Whisper-compatible speech-to-text endpoint to the FastAPI proxy.
Clients upload an audio file with a model identifier, 9Router resolves the
provider, forwards to the upstream transcription API, and returns the text.

```
Client → POST /v1/audio/transcriptions (multipart: file + model + options)
           ↓
       parse model → provider "openai" + model "whisper-1"
           ↓
       DB lookup → find active connection with API key
           ↓
       forward audio to upstream STT API (format varies per provider)
           ↓
       return { text: "transcribed text..." }
```

---

## Key Differences From Other Endpoints

STT is the most different endpoint in the entire v1 proxy surface:

1. **Multipart form data** — NOT JSON. The client uploads an audio file along
   with form fields. FastAPI receives via `UploadFile` + `Form()` parameters.

2. **6 completely different provider APIs** — each STT provider has its own
   request format, auth method, and response shape. No simple path swap.

3. **File size limits** — audio files can be large (up to 100MB for long
   recordings). Must configure Uvicorn upload limit.

4. **Timeout** — AssemblyAI requires async polling up to 120 seconds. Must
   configure httpx timeout accordingly.

5. **Response normalization** — each provider returns a different shape.
   Must normalize to OpenAI format `{ text: "..." }`.

---

## Supported Providers & Their APIs

### Group A: OpenAI Whisper-Compatible (standard multipart)

These accept the same multipart format: `file`, `model`, `language`, `prompt`,
`response_format`, `temperature`. Response is JSON `{ text }`.

| Provider | Upstream URL                                          | Auth Header | Notes                       |
|----------|------------------------------------------------------|-------------|-----------------------------|
| openai   | https://api.openai.com/v1/audio/transcriptions       | Bearer      | Default STT provider        |
| groq     | https://api.groq.com/openai/v1/audio/transcriptions  | Bearer      | Faster inference, same API  |
| azure    | {endpoint}/openai/deployments/{dep}/audio/transcriptions | api-key  | Custom URL with deployment  |

### Group B: Provider-Specific Adapters

| Provider     | Upstream URL                                           | Auth              | Request Format                                    | Response Shape                                      |
|-------------|-------------------------------------------------------|--------------------|---------------------------------------------------|-----------------------------------------------------|
| deepgram    | https://api.deepgram.com/v1/listen?model={m}&smart_format=true | Token         | Raw binary POST, model as query param              | `{ results.channels[0].alternatives[0].transcript }` |
| gemini      | https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k} | query param | JSON with base64 inline_data audio | `{ candidates[0].content.parts[0].text }` |
| assemblyai  | https://api.assemblyai.com/v2/transcript              | Bearer             | 3-step async: upload → submit → poll (max 120s)   | `{ text }` after polling                            |
| huggingface | https://api-inference.huggingface.co/models/{m}       | Bearer             | Raw binary POST to model-specific URL             | `{ text }`                                          |
| nvidia      | https://integrate.api.nvidia.com/v1/audio/transcriptions | Bearer          | Multipart form data (file + model)                | `{ text }` or `{ transcript }`                      |

### Provider Dispatch Table (from `sttCore.js`)

```javascript
switch (cfg.format) {
  case "deepgram":        return transcribeDeepgram(...)
  case "assemblyai":      return transcribeAssemblyAI(...)
  case "nvidia-asr":      return transcribeNvidia(...)
  case "huggingface-asr": return transcribeHuggingFace(...)
  case "gemini-stt":      return transcribeGemini(...)
  default:                return transcribeOpenAICompatible(...)  // openai, groq, azure
}
```

---

## Request / Response Format

**Request (multipart/form-data):**
```bash
POST /v1/audio/transcriptions
Authorization: Bearer <jwt_or_api_key>
Content-Type: multipart/form-data

file:              [binary audio data]     # required — mp3, wav, ogg, flac, webm, m4a, aac, opus
model:             openai/whisper-1        # required — format: {alias}/{model_id}
language:          en                      # optional — ISO 639-1 code
prompt:            "Technical terms..."    # optional — context hint for Whisper
response_format:   json                    # optional — json, text, srt, vtt, verbose_json
temperature:       0                       # optional — 0.0 to 1.0
```

**Response (OpenAI format):**
```json
{
  "text": "Hello world, this is the transcribed text."
}
```

**Response (verbose_json, only for Whisper-compatible providers):**
```json
{
  "task": "transcribe",
  "language": "english",
  "duration": 5.2,
  "text": "Hello world, this is the transcribed text.",
  "segments": [
    { "id": 0, "start": 0.0, "end": 5.2, "text": "Hello world, this is the transcribed text." }
  ]
}
```

---

## Phase 1 — Backend: Create STT Adapters

**New file:** `backend/app/services/stt_adapters.py`

This file contains one adapter function per provider group. Each function
takes the audio bytes + metadata and returns `{ text }`.

### 1.1 OpenAI Whisper-Compatible Adapter

```python
async def stt_openai_compatible(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    model: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    language: str = None,
    prompt: str = None,
    response_format: str = None,
    temperature: float = None,
) -> dict:
    """Standard Whisper-compatible multipart transcription."""
    import io
    
    files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
    data = {"model": model}
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    if response_format:
        data["response_format"] = response_format
    if temperature is not None:
        data["temperature"] = str(temperature)
    
    resp = await client.post(base_url, headers=headers, files=files, data=data)
    resp.raise_for_status()
    return resp.json()  # { text } or verbose_json
```

Used by: openai, groq, azure.

### 1.2 Deepgram Adapter

Deepgram accepts raw binary audio with model as query parameter:

```python
async def stt_deepgram(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str = None,
) -> dict:
    """Deepgram STT — raw binary POST with query params."""
    url = f"{base_url}?model={model}&smart_format=true&punctuate=true"
    if language:
        url += f"&language={language}"
    else:
        url += "&detect_language=true"
    
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type,
    }
    
    resp = await client.post(url, content=file_bytes, headers=headers)
    resp.raise_for_status()
    
    data = resp.json()
    transcript = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
    return {"text": transcript}
```

### 1.3 Gemini STT Adapter

Gemini uses `generateContent` with audio as base64 inline data:

```python
async def stt_gemini(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str = None,
    prompt: str = None,
) -> dict:
    """Gemini STT — generateContent with inline audio data."""
    import base64
    
    b64_audio = base64.b64encode(file_bytes).decode()
    
    default_prompt = "Generate a transcript of the speech. Return only the transcribed text, no commentary."
    if prompt:
        default_prompt = prompt
    if language:
        default_prompt += f" Language: {language}."
    
    url = f"{base_url}/{model}:generateContent?key={api_key}"
    body = {
        "contents": [{
            "parts": [
                {"text": default_prompt},
                {"inline_data": {"mime_type": content_type, "data": b64_audio}},
            ]
        }],
    }
    
    resp = await client.post(url, json=body)
    resp.raise_for_status()
    
    data = resp.json()
    text = "".join(
        p.get("text", "")
        for p in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        if "text" in p
    )
    return {"text": text}
```

### 1.4 AssemblyAI Adapter (Async Polling)

AssemblyAI requires 3 steps: upload audio → submit transcription → poll for result.

```python
async def stt_assemblyai(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str = None,
) -> dict:
    """AssemblyAI STT — 3-step async: upload, submit, poll (max 120s)."""
    import asyncio
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Step 1: Upload audio file
    upload_resp = await client.post(
        "https://api.assemblyai.com/v2/upload",
        content=file_bytes,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json()["upload_url"]
    
    # Step 2: Submit transcription job
    submit_body = {
        "audio_url": upload_url,
        "speech_models": [model],
        "language_detection": True,
    }
    submit_resp = await client.post(
        base_url,  # https://api.assemblyai.com/v2/transcript
        json=submit_body,
        headers={**headers, "Content-Type": "application/json"},
    )
    submit_resp.raise_for_status()
    transcript_id = submit_resp.json()["id"]
    
    # Step 3: Poll for completion (max 120s, every 2s)
    poll_url = f"{base_url}/{transcript_id}"
    for _ in range(60):  # 60 * 2s = 120s
        await asyncio.sleep(2)
        poll_resp = await client.get(poll_url, headers=headers)
        if poll_resp.status_code != 200:
            continue
        
        result = poll_resp.json()
        if result["status"] == "completed":
            return {"text": result.get("text", "")}
        elif result["status"] == "error":
            raise Exception(result.get("error", "AssemblyAI transcription failed"))
    
    raise Exception("AssemblyAI transcription timeout after 120s")
```

### 1.5 HuggingFace Adapter

```python
async def stt_huggingface(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
) -> dict:
    """HuggingFace STT — raw binary POST to model-specific URL."""
    url = f"{base_url}/{model}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type,
    }
    
    resp = await client.post(url, content=file_bytes, headers=headers)
    resp.raise_for_status()
    return resp.json()
```

### 1.6 NVIDIA Adapter

```python
async def stt_nvidia(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> dict:
    """NVIDIA NIM STT — multipart form data."""
    import io
    
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
    data = {"model": model}
    
    resp = await client.post(base_url, headers=headers, files=files, data=data)
    resp.raise_for_status()
    
    result = resp.json()
    return {"text": result.get("text") or result.get("transcript", "")}
```

### 1.7 Dispatch Table

```python
STT_ADAPTERS = {
    # OpenAI Whisper-compatible (default)
    "openai": stt_openai_compatible,
    "groq": stt_openai_compatible,
    # Provider-specific
    "deepgram": stt_deepgram,
    "gemini": stt_gemini,
    "assemblyai": stt_assemblyai,
    "huggingface": stt_huggingface,
    "nvidia": stt_nvidia,
}

def get_stt_adapter(provider: str):
    return STT_ADAPTERS.get(provider)
```

---

## Phase 2 — Backend: MIME Type Helper

Audio files need correct MIME type for each provider. Add helper:

```python
AUDIO_MIME_MAP = {
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
    "aac": "audio/aac",
    "opus": "audio/opus",
}

def resolve_audio_mime(filename: str, declared_type: str = "") -> str:
    """Resolve audio MIME type from filename or declared Content-Type."""
    if declared_type and declared_type.startswith("audio/"):
        return declared_type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return AUDIO_MIME_MAP.get(ext, "application/octet-stream")
```

---

## Phase 3 — Backend: Add `/v1/audio/transcriptions` Route

**File:** `backend/app/routers/v1_proxy.py`

### 3.1 The Route Handler

```python
@router.post("/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """OpenAI Whisper-compatible STT proxy (multipart form data)."""
    from fastapi import UploadFile, Form
    from app.services.stt_adapters import get_stt_adapter, resolve_audio_mime
    
    # Parse multipart form data
    form = await request.form()
    file: UploadFile = form.get("file")
    model_str: str = form.get("model", "")
    language: str = form.get("language", "")
    prompt: str = form.get("prompt", "")
    response_format: str = form.get("response_format", "")
    temperature: str = form.get("temperature", "")
    
    if not file:
        raise HTTPException(status_code=400, detail="Missing required field: file")
    if not model_str:
        raise HTTPException(status_code=400, detail="Missing required field: model")
    
    # Parse provider from model string (e.g. "openai/whisper-1")
    if "/" not in model_str:
        raise HTTPException(status_code=400, detail="Model must be in provider/model format")
    
    provider_name, model_id = model_str.split("/", 1)
    provider_id = ALIAS_TO_ID.get(provider_name, provider_name)
    
    # DB lookup: find active connection
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == provider_id, ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    
    if not connections:
        raise HTTPException(status_code=503, detail=f"No connection for provider: {provider_id}")
    
    # Read file bytes + resolve MIME type
    file_bytes = await file.read()
    filename = file.filename or "audio.wav"
    content_type = resolve_audio_mime(filename, file.content_type or "")
    
    # Get adapter
    adapter = get_stt_adapter(provider_id)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_id}' does not support STT")
    
    # Credential fallback loop (same pattern as chat)
    last_error = None
    for conn in connections:
        data = json.loads(conn.data) if conn.data else {}
        api_key = data.get("apiKey", "")
        base_url = data.get("baseUrl") or PROVIDER_DEFAULTS.get(provider_id, {}).get("baseUrl", "")
        
        try:
            # Build headers per provider
            cfg = PROVIDER_CONFIGS.get(provider_id, PROVIDER_CONFIGS.get("openai", {}))
            headers = {cfg.get("auth_header", "Authorization"): f"{cfg.get('auth_prefix', 'Bearer ')}{api_key}"}
            
            result = await adapter(
                client=httpx.AsyncClient(timeout=180.0),  # longer timeout for audio
                base_url=_build_stt_url(provider_id, base_url, data, model_id, api_key),
                headers=headers if provider_id not in ("deepgram",) else {},
                api_key=api_key,
                model=model_id,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                language=language or None,
                prompt=prompt or None,
                response_format=response_format or None,
                temperature=float(temperature) if temperature else None,
            )
            
            return JSONResponse(content=result)
            
        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if e.response.status_code < 500:
                return JSONResponse(status_code=e.response.status_code, content={"error": {"message": e.response.text[:500]}})
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)}
            continue
    
    error_msg = last_error.get("detail", "All STT providers failed") if last_error else "No targets"
    error_status = last_error.get("status", 502) if last_error else 502
    return JSONResponse(status_code=error_status, content={"error": {"message": error_msg}})
```

### 3.2 STT URL Builder Helper

```python
def _build_stt_url(provider: str, base_url: str, data: dict, model: str, api_key: str = "") -> str:
    """Build upstream STT URL per provider."""
    if provider == "deepgram":
        return f"{base_url}?model={model}&smart_format=true&punctuate=true"
    elif provider == "gemini":
        return f"{base_url}/{model}:generateContent?key={api_key}"
    elif provider == "assemblyai":
        return "https://api.assemblyai.com/v2/transcript"
    elif provider == "huggingface":
        return f"{base_url}/{model}"
    elif provider == "azure":
        endpoint = data.get("azureEndpoint") or base_url
        deployment = data.get("deployment", "whisper")
        api_version = data.get("apiVersion", "2024-06-01")
        return f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/audio/transcriptions?api-version={api_version}"
    else:
        # Default: OpenAI-compatible
        return f"{base_url}/audio/transcriptions"
```

### 3.3 Upload Size Configuration

FastAPI/Starlette default upload limit is ~1MB. Audio files need more.

**File:** `backend/app/main.py`

```python
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

class LimitUploadSize(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int = 100 * 1024 * 1024):  # 100MB
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_upload_size:
            return JSONResponse(
                status_code=413,
                content={"error": {"message": f"File too large. Max size: {self.max_upload_size // (1024*1024)}MB"}},
            )
        return await call_next(request)
```

---

## Phase 4 — Frontend: No Changes Required

The `/v1/audio/transcriptions` endpoint is a pure API endpoint. No UI changes
needed. MediaProvidersPage already shows STT providers filtered by
`serviceKinds: ["stt"]`.

**Optional future enhancement:** Add a "Test STT" upload button in
ProviderDetailPage for STT providers. Out of scope.

---

## Phase 5 — Testing

### 5.1 Prepare Test Audio File

Create or obtain a short audio file for testing:

```bash
# Generate a 5-second test tone (if no audio file available)
# Or use any .mp3/.wav/.ogg file
ls -la test_audio.mp3
```

### 5.2 Manual curl tests

Get token first:
```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — OpenAI Whisper (happy path):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=openai/whisper-1" \
  -F "language=en" | jq .
```
Expected: `{"text": "Hello world..."}`

**Test 2 — Groq Whisper:**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=groq/whisper-large-v3" | jq .
```

**Test 3 — Deepgram:**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=deepgram/nova-3" | jq .
```

**Test 4 — Gemini STT:**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=gemini/gemini-2.5-flash" | jq .
```

**Test 5 — AssemblyAI (async polling):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=assemblyai/universal-3-pro" \
  --max-time 130 | jq .
```
Expected: Waits up to 120s, returns `{"text": "..."}`.

**Test 6 — Missing file (400):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "model=openai/whisper-1" | jq .
```
Expected: `400` with `"Missing required field: file"`

**Test 7 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" | jq .
```
Expected: `400` with `"Missing required field: model"`

**Test 8 — No connection (503):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=nonexistent/whisper-1" | jq .
```
Expected: `503` with `"No connection for provider: nonexistent"`

**Test 9 — Unsupported provider (400):**
```bash
curl -s -X POST http://localhost:9000/v1/audio/transcriptions \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_audio.mp3" \
  -F "model=cursor/whisper-1" | jq .
```
Expected: `400` with `"Provider 'cursor' does not support STT"`

**Test 10 — Verify console log:**
```bash
curl -s http://localhost:9000/console/logs \
  -H "Authorization: Bearer $TOKEN" | jq '.[-1]'
```
Expected: log entry shows `POST /v1/audio/transcriptions → 200`.

### 5.3 Verify in running app

1. Open http://localhost:5173
2. Navigate to Media Providers → Speech to Text
3. Confirm STT providers still display correctly — no regressions
4. Check Console Log page — curl requests should appear

### 5.4 Regression check

Confirm existing endpoints still work:

```bash
# Chat completions
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'

# Embeddings (if already ported)
curl -s -X POST http://localhost:9000/v1/embeddings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/text-embedding-3-small", "input": "Hello"}' \
  | jq '.data[0].embedding | length'
```

---

## Phase 6 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/audio/transcriptions` from
   "Not Yet Ported" table to "Fully Ported" table.

2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 3 as done:
   change `POST /v1/audio/transcriptions` status to ✅.

3. **`docs/plans/v1-audio-transcriptions.md`** (this file) — Update status at
   top from `Not started` to `Done`, add completion date and notes.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Upload size limit | Default Uvicorn/Starlette limit ~1MB. Must add middleware or increase Uvicorn `--limit-max-request-size 104857600` (100MB) in Docker command. |
| AssemblyAI timeout | 120s polling. For very long audio files, may need to increase. Consider making it configurable. |
| AssemblyAI async model | The original uses async polling. In FastAPI, this blocks the request thread. Consider making it a background task with callback URL in future. |
| Deepgram language detection | When no `language` param provided, original adds `detect_language=true`. This may add latency. |
| Gemini STT uses `generateContent` | Not a dedicated STT API — repurposes the chat API with audio modality. May behave differently from true STT APIs. |
| Azure STT | URL pattern depends on deployment name. Need to handle `providerSpecificData` for deployment config. |
| HuggingFace model ID | Supports `facebook/mms-tts-eng`, `openai/whisper-large-v3` etc. URL is `{baseUrl}/{modelId}`. |
| `response_format` passthrough | Only supported by OpenAI-compatible providers. Others ignore it. |
| `temperature` passthrough | Only supported by OpenAI-compatible providers. Others ignore it. |
| Concurrent uploads | Large audio files may cause memory pressure. Consider streaming upload in future. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/stt_adapters.py` | NEW — All STT provider adapters, MIME helper, dispatch table |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/audio/transcriptions` handler, `_build_stt_url()` helper |
| `backend/app/main.py` | Add upload size limit middleware |
| `docs/porting-status.md` | Move STT endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 3 done |
| `docs/plans/v1-audio-transcriptions.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies (httpx already installed).

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Multipart parsing | Medium | FastAPI `form()` + `UploadFile`, different from JSON endpoints |
| OpenAI/Groq adapter | Low | Standard Whisper multipart, well-documented |
| Deepgram adapter | Low | Raw binary POST, model as query param |
| Gemini adapter | Medium | Base64 encoding, `generateContent` API, text extraction from nested response |
| AssemblyAI adapter | High | 3-step async flow, polling loop, 120s timeout |
| HuggingFace adapter | Low | Raw binary POST to model URL |
| NVIDIA adapter | Low | Multipart, simple response normalization |
| URL builder | Medium | 6 different URL patterns |
| Upload size config | Low | Middleware or Uvicorn flag |
| Error handling | Medium | Each provider returns errors differently |

**Overall:** Medium complexity. The main challenge is the 6 different provider
APIs. The route handler itself is straightforward multipart parsing + fallback
loop. AssemblyAI's async polling is the most complex adapter.

**Recommended implementation order:**
1. OpenAI + Groq (standard Whisper — simplest)
2. Deepgram (raw binary — simple)
3. Gemini (base64 inline — medium)
4. HuggingFace + NVIDIA (simple variants)
5. AssemblyAI (async polling — most complex, do last)

---

## Implementation Notes (Iterasi 1 — actual deviations from plan)

The implementation followed the spirit of this plan but deviated on several details to align with the existing codebase patterns (especially the TTS handler in `v1_proxy.py`). Recorded here so future iterations know the real shape of the code.

### 1. Provider resolution helpers
Plan called for `ALIAS_TO_ID.get(...)` and `PROVIDER_DEFAULTS.get(...)`. Those don't exist. The codebase uses:
- `_resolve_provider_alias(provider_name)` from `app.services.proxy`
- `_resolve_base_url(provider_id, conn_data)` from `app.services.proxy`

The STT route uses these instead.

### 2. Connection data parsing
Plan accessed `data.get("apiKey", "")` only. Existing convention (TTS handler, chat handler) falls back to `api_key` snake_case as well:
```python
api_key = conn_data.get("apiKey") or conn_data.get("api_key") or ""
```

### 3. httpx.AsyncClient lifecycle
Plan instantiated `httpx.AsyncClient(timeout=180.0)` inside the fallback loop without `async with` — that leaks connections. The implementation follows the TTS pattern: one `async with httpx.AsyncClient(timeout=180.0) as client:` wrapping the whole fallback loop.

### 4. Adapter signature: kwargs-only with `**_kwargs`
Plan had positional/keyword mixed signatures with provider-specific kwargs. The implementation makes every adapter accept kwargs-only with a `**_kwargs` catch-all, so the route handler can pass the same set of kwargs to any adapter (the adapter ignores what it doesn't need). This mirrors `tts_adapters.py`.

### 5. Header construction
Plan called for a `PROVIDER_CONFIGS` table to build auth headers. That table doesn't exist. The implementation passes `auth_header` and `auth_prefix` kwargs to the OpenAI-compatible adapter (default `Authorization` / `Bearer `, Azure overrides to `api-key` / empty). Other adapters build their headers internally (e.g. Deepgram uses `Token`, AssemblyAI uses raw key without prefix).

### 6. AssemblyAI specifics
- Auth header is `Authorization: <raw_key>` — NO `Bearer ` prefix (plan had Bearer, this is wrong per AssemblyAI docs).
- Field is `speech_model` (singular), not `speech_models` (plural) as the plan stated.
- Language uses `language_code` (ISO 639-1) plus optional `language_detection=true` fallback.
- URL is hardcoded inside the adapter (not via `_build_stt_url`). `assemblyai` is in `_FIXED_URL_STT_PROVIDERS` so the empty-base_url guard skips it.

### 7. URL builder
Instead of a separate `_build_stt_url()` helper, URL construction lives inside each adapter (where it belongs — adapters know their own API shape). The route handler only computes Azure's `extra_url` (deployment + api-version) and passes it as a kwarg to the OpenAI-compatible adapter.

### 8. Upload-size middleware — SKIPPED
Plan called for a `LimitUploadSize` middleware and/or Uvicorn `--limit-max-request-size 104857600` flag.

- **Uvicorn does NOT have a `--limit-max-request-size` flag.** Available limit flags: `--limit-concurrency`, `--limit-max-requests`, `--h11-max-incomplete-event-size`. None of them cap body size.
- Starlette/FastAPI's default body handling has no hard size limit — the request size is bounded only by available memory/disk.
- Adding a `LimitUploadSize` middleware now would create a false ceiling without a clear product requirement. Deferred until needed.

If a future iteration needs a hard cap, the simplest path is a small Starlette middleware that checks `Content-Length` and returns 413 if it exceeds the configured max. The middleware code from the original plan is still valid; we just didn't wire it in yet.

### 9. ValueError handling
Adapters raise `ValueError` for adapter-level validation problems (missing model, missing key, malformed input). The route handler catches `ValueError` and returns 400 to the client — this is a client mistake, not an upstream failure, so the fallback loop should NOT swallow it and move to the next connection. The behaviour matches what users expect when they send a clearly malformed request.

### 10. HuggingFace multi-slash model IDs
HF model IDs like `openai/whisper-large-v3` contain a slash. The route parses `provider/model` with `split("/", 1)` so the entire remainder (including slashes) becomes the model id. The HF adapter rejects `..` segments to prevent path traversal.

### 11. response_format = text/srt/vtt
For Whisper-compatible providers, when the client sets `response_format=text` (or srt/vtt), the upstream returns plain text, not JSON. The adapter detects this and returns `{"text": resp.text}` instead of `resp.json()` (which would crash).

---

## Iterasi 1 Verification Results

Smoke-tested via curl against the running dev backend (no real upstream provider credentials wired up yet):

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Missing `file` field | 400 + "Missing required field: file" | 400 + matching detail | ✅ |
| Missing `model` field | 400 + "Missing required field: model" | 400 + matching detail | ✅ |
| Model without `/` | 400 + "Model must be in 'provider/model' format" | 400 + matching detail | ✅ |
| Unsupported provider (`cursor/whisper-1`) | 501 + provider list | 501 with `assemblyai, azure, deepgram, gemini, groq, huggingface, nvidia, openai` listed | ✅ |
| No DB connection (`huggingface/...`) | 503 + "No active connection" | 503 + matching detail | ✅ |
| Invalid temperature value (`not-a-number`) | 400 + "Invalid temperature value" | 400 + matching detail | ✅ |
| Endpoint registered in OpenAPI spec | listed under `/v1/audio/transcriptions` | confirmed via `/openapi.json` | ✅ |

**Iterasi 2 follow-ups:**
- ✅ ~~Live smoke test against at least one real provider~~ — Groq Whisper verified end-to-end.
- ✅ ~~Verify gemini STT~~ — Verified end-to-end (5/5 tests pass, see below).
- ❌ ~~Verify nvidia STT~~ — **Removed from dispatch.** Original 9router providers.js does NOT declare `stt` in nvidia's `serviceKinds` (only `llm, tts, embedding`). Probe of `https://integrate.api.nvidia.com/v1/audio/transcriptions` returns "404 page not found" — no public OpenAI-compatible STT endpoint exists. NVIDIA Riva ASR uses gRPC, not REST. The `stt_nvidia()` adapter function is kept in `stt_adapters.py` for potential future Riva integration but NOT registered in `STT_ADAPTERS`. NVIDIA STT requests now correctly return 501.
- ✅ ~~Verify AssemblyAI polling end-to-end with a real ~5s audio clip~~ — Verified (5/5 tests pass, see below).
- Verify OpenAI Whisper (needs key in DB first).
- ✅ ~~Verify Deepgram~~ — Verified end-to-end (6/6 tests pass, see below).
- Verify HuggingFace ASR (needs key in DB first).
- Verify Azure (needs deployment + endpoint + key in DB first).
- Consider an upload-size cap middleware if/when needed.
- Optional: add a "Test STT" upload button in ProviderDetailPage for STT providers (out of scope).

---

## Iterasi 2 Live Verification — Groq Whisper

Test audio: `/usr/share/sounds/alsa/Front_Center.wav` (built-in Linux sample, ~1.4s, speaks "Front Center").

| # | Test | Form Fields | Expected | Actual | Status |
|---|------|-------------|----------|--------|--------|
| 1 | Happy path | `model=groq/whisper-large-v3-turbo` | 200 + `{text}` | `{"text":" Front, center.","x_groq":{"id":"..."}}` (511ms) | ✅ |
| 2 | With language hint | `+ language=en` | 200 + same text | identical (440ms) | ✅ |
| 3 | Verbose JSON | `+ response_format=verbose_json` | 200 + segments/tokens | `{task, language:"English", duration:1.42, text, segments:[{id,seek,start,end,text,tokens,temperature,avg_logprob,...}]}` (388ms) | ✅ |
| 4 | Plain text response | `+ response_format=text` | 200 + wrapped `{text}` | `{"text":" Front, center."}` — adapter correctly handles non-JSON upstream response (393ms) | ✅ |
| 5 | Bogus upstream model | `model=groq/whisper-nonexistent-v99` | 404 with upstream error, NO fallback | HTTP 404 + upstream `model_not_found` error verbatim (209ms) | ✅ |
| 6 | With prompt hint | `+ prompt=...` | 200 + same text | identical (405ms) | ✅ |

**Conclusion:** Groq STT works end-to-end. Multipart parsing, language/prompt/response_format passthrough, verbose_json segments, plain-text response handling, and 4xx no-fallback behaviour all verified. Ready to move on to gemini + nvidia.

---

## Iterasi 2 Live Verification — Gemini STT

Same test audio (`Front_Center.wav`). Gemini repurposes `generateContent` for STT via base64 `inline_data` + a transcription prompt — slower than Groq (~3–5s vs ~0.4s) but works.

| # | Test | Form Fields | Expected | Actual | Status |
|---|------|-------------|----------|--------|--------|
| 1 | Happy path (2.5-flash) | `model=gemini/gemini-2.5-flash` | 200 + `{text}` | `{"text":"Front. Center."}` (4.7s) | ✅ |
| 2 | 2.0-flash (free tier) | `model=gemini/gemini-2.0-flash` | 429 (quota=0 free tier) | 429 with upstream quota error verbatim (0.2s) | ✅ (handled correctly) |
| 3 | With language hint | `+ language=en` | 200 + text, language appended to instruction | `{"text":"front, center"}` (2.8s) | ✅ |
| 4 | Custom prompt override | `+ prompt=Transcribe... lowercase, no punctuation` | Model obeys custom instruction | `{"text":"front center"}` — **lowercase, no period** (4.8s) | ✅ |
| 5 | Bogus model name | `model=gemini/gemini-nonexistent-v99` | 404, no fallback | HTTP 404 + upstream `NOT_FOUND` verbatim (0.2s) | ✅ |

**Notes:**
- Gemini adapter correctly uses `?key=<api_key>` query param auth, base64-encodes audio into `inline_data`, and extracts text from `candidates[0].content.parts[].text`.
- `prompt` field properly overrides the default `"Generate a transcript of the speech..."` instruction.
- `language` field is appended to the instruction (e.g. `"Language: en."`) — Gemini doesn't have a structured language field for STT.
- 2.0-flash free tier has `limit: 0` — use 2.5-flash for actual STT work, or upgrade billing.

---

## Iterasi 2 Live Verification — Deepgram

Same test audio (`/usr/share/sounds/alsa/Front_Center.wav`). Deepgram uses `Token` auth prefix (not `Bearer`), raw binary POST to `https://api.deepgram.com/v1/listen` with model as query param.

**Bug fixed during verification:** Deepgram was missing from `_FIXED_URL_STT_PROVIDERS` in `app/services/stt_adapters.py`. The route handler at `v1_proxy.py:784` rejected requests with `"No base_url for provider deepgram"` before the adapter (which has a hardcoded fallback URL) could run. Added `deepgram` and `huggingface` to the set since both adapters embed their own URLs.

| # | Test | Form Fields | Expected | Actual | Status |
|---|------|-------------|----------|--------|--------|
| 1 | Happy path nova-2 | `model=deepgram/nova-2 language=en` | 200 + `{text}` | `{"text":"Front, center."}` (2.6s) | ✅ |
| 2 | Without language hint | `model=deepgram/nova-2` | 200 + text, auto-detect language | `{"text":"Front, center.","language":"en"}` (1.9s) | ✅ |
| 3 | nova-3 (newer model) | `model=deepgram/nova-3 language=en` | 200 + text | `{"text":"Front center."}` (2.0s) | ✅ |
| 4 | With prompt (ignored — Deepgram has no prompt field) | `+ prompt=test` | 200 + text, prompt silently dropped | `{"text":"Front, center."}` (2.1s) | ✅ |
| 5 | Bogus upstream model | `model=deepgram/nonexistent-v99` | 4xx + upstream error, no fallback | HTTP 403 + Deepgram `INSUFFICIENT_PERMISSIONS` verbatim (1.4s) | ✅ (handled correctly) |
| 6 | verbose_json response_format | `+ response_format=verbose_json` | 200 + text (Deepgram returns flat `{text}` only — segments not extracted) | `{"text":"Front, center."}` (2.2s) | ✅ |

**Notes:**
- Deepgram auto-detects language when `language` form field omitted (returns `language` field in response).
- Deepgram has no analog to OpenAI's `prompt` parameter for transcription — silently ignored.
- `response_format=verbose_json` returns the same simple `{text}` shape. Future enhancement: map Deepgram's `results.channels[0].alternatives[0].words[]` to verbose_json segments.
- Bogus model returns 403 (INSUFFICIENT_PERMISSIONS) rather than 404 — Deepgram's API behaviour. Error propagates verbatim, no fallback triggered.

---

## Iterasi 2 Live Verification — AssemblyAI

Same test audio (`/usr/share/sounds/alsa/Front_Center.wav`). AssemblyAI is **async**: adapter uploads file → submits transcript job → polls `/v2/transcript/{id}` until `status=completed`. Auth uses raw `Authorization: {key}` (no `Bearer` prefix).

**Bug fixed during verification:** AssemblyAI API deprecated the `speech_model` (singular string) field in 2025 — adapter was sending `speech_model: "best"` which returned `400 "speech_model is deprecated. Use 'speech_models' instead"`. Patched `stt_assemblyai()` in `app/services/stt_adapters.py` to send `speech_models: [model]` (plural array). Additionally, valid model values changed: old `best/nano/universal` → new `universal-2/universal-3-pro`.

| # | Test | Form Fields | Expected | Actual | Status |
|---|------|-------------|----------|--------|--------|
| 1 | Happy path universal-2 | `model=assemblyai/universal-2 language=en` | 200 + `{text, language}` | `{"text":"Front center.","language":"en_us"}` (4.4s) | ✅ |
| 2 | universal-3-pro (newer) | `model=assemblyai/universal-3-pro language=en` | 200 + text | `{"text":"Front, center.","language":"en_us"}` (4.1s) | ✅ |
| 3 | Without language hint | `model=assemblyai/universal-2` | 200 + text, language auto-detected | `{"text":"Front center.","language":"en"}` (4.1s) | ✅ |
| 4 | With prompt (ignored — AssemblyAI has no prompt field) | `+ prompt=test` | 200 + text, prompt silently dropped | `{"text":"Front center.","language":"en_us"}` (4.1s) | ✅ |
| 5 | Bogus upstream model | `model=assemblyai/nonexistent-v99` | 4xx + upstream error, no fallback | HTTP 400 + AssemblyAI `"speech_models must be one of: universal-3-pro, universal-2"` verbatim (1.9s) | ✅ (handled correctly) |

**Notes:**
- Polling overhead adds ~4s for a 1.4s audio clip. Real-world latency scales with audio length (AssemblyAI docs claim ~0.4× realtime for `universal-2`).
- `language_code=en` → response `language=en_us` (AssemblyAI returns a locale-specific code).
- Adapter polls every 2s, with a 120s overall timeout in `v1_proxy.py` (`httpx.AsyncClient(timeout=180.0)` covers worst case).
- `language` form field maps to `language_code`; omitting it triggers AssemblyAI's auto-detect (`language_detection=true`).
- Adapter returns minimal `{text, language}` shape. Word-level timestamps in `words[]` are available from AssemblyAI but not extracted — could be a future enhancement for `response_format=verbose_json`.

