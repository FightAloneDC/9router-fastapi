# Plan: POST /v1/images/generations

**Status:** Not started  
**Parent plan:** `docs/plans/v1-proxy-endpoints.md`  
**Original source:** `~/dev/9router/src/app/api/v1/images/generations/route.js` → `src/sse/handlers/imageGeneration.js` → `open-sse/handlers/imageGenerationCore.js`  
**Estimated effort:** High — 14 provider adapters with wildly different APIs, async polling for 2 providers, SSE streaming for Codex, binary response handling.

---

## What This Does

Adds an OpenAI-compatible image generation endpoint to the FastAPI proxy.
Clients send a prompt + model, 9Router resolves the provider, forwards to the
upstream image generation API, and returns image data (URL or base64).

```
Client → POST /v1/images/generations { model: "openai/dall-e-3", prompt: "A cat" }
           ↓
       parse model → provider "openai" + model "dall-e-3"
           ↓
       DB lookup → find active connection with API key
           ↓
       forward to upstream image API (format varies per provider)
           ↓
       return { created: 1234, data: [{ url: "https://..." }] }
         or  { created: 1234, data: [{ b64_json: "..." }] }
```

---

## Key Characteristics

1. **JSON in, JSON out** — unlike STT (multipart) or TTS (binary), image
   generation uses standard JSON request/response.

2. **14 provider adapters** — the most adapters of any endpoint. Each has its
   own URL, body format, and response parsing.

3. **Two async polling providers** — Fal.ai and NanoBanana require submit →
   poll → fetch result pattern (similar to AssemblyAI for STT).

4. **Codex SSE streaming** — Codex (ChatGPT) image generation streams the
   image via SSE, accumulating base64 chunks. Most complex adapter.

5. **Response normalization** — must normalize to OpenAI format:
   `{ created, data: [{ url }] }` or `{ created, data: [{ b64_json }] }`.

6. **Combo support** — the original supports combo expansion for image models
   (fallback/round-robin across multiple providers).

7. **Binary output mode** — `?response_format=binary` returns raw image bytes
   instead of JSON (used by MediaProviderDetailPage for preview).

---

## Supported Providers & Their APIs

### Group A: OpenAI-Compatible (simplest — standard `/images/generations`)

These use the same body format: `{ model, prompt, n, size, quality, style, response_format }`.

| Provider    | Upstream URL                                          | Auth     | Notes                     |
|------------|------------------------------------------------------|----------|---------------------------|
| openai     | https://api.openai.com/v1/images/generations         | Bearer   | DALL·E 3, gpt-image-1     |
| openrouter | https://openrouter.ai/api/v1/images/generations      | Bearer   | Multi-provider passthrough |
| minimax    | https://api.minimaxi.com/v1/images/generations       | Bearer   | MiniMax image models      |
| siliconflow | https://api.siliconflow.cn/v1/images/generations    | Bearer   | SiliconFlow image models  |

### Group B: Provider-Specific (custom URL/body/response)

| Provider       | Upstream URL                                          | Auth              | Body Format                              | Response Format                   |
|---------------|------------------------------------------------------|--------------------|------------------------------------------|------------------------------------|
| fal-ai        | https://queue.fal.run/{model}                        | Key                | `{ prompt, num_images, image_size }`     | Async: submit → poll → fetch result |
| stability-ai  | https://api.stability.ai/v2beta/stable-image/generate/{endpoint} | Bearer | `{ prompt, output_format, aspect_ratio }` | `{ image: "<b64>" }` |
| gemini        | https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k} | query param | `{ contents, generationConfig.responseModalities: ["TEXT","IMAGE"] }` | `{ candidates[0].content.parts[].inlineData.data }` |
| huggingface   | https://api-inference.huggingface.co/models/{model}  | Bearer             | `{ inputs: prompt }`                     | Binary image bytes → base64       |
| cloudflare-ai | https://api.cloudflare.com/client/v4/accounts/{id}/ai/run/{model} | Bearer | `{ prompt, width, height }` or multipart | `{ result.image: "<b64>" }` or binary |
| nanobanana    | https://api.nanobananaapi.ai/api/v1/nanobanana/generate | Bearer          | `{ prompt, type, numImages, image_size }` | Async: submit → poll → `{ response.resultImageUrl }` |
| codex         | https://chatgpt.com/backend-api/codex/responses      | OAuth token (Bearer) | Complex: Responses API with input_image refs | SSE stream → accumulate base64 chunks |

### Group C: Local/NoAuth (localhost services)

| Provider | Upstream URL                  | Auth  | Notes                                    |
|----------|------------------------------|-------|------------------------------------------|
| sdwebui  | http://localhost:7860/sdapi/v1/txt2img | None | Stable Diffusion WebUI local server |
| comfyui  | http://localhost:8188/prompt  | None  | ComfyUI local workflow server            |

---

## Request / Response Format

**Request:**
```json
POST /v1/images/generations
Authorization: Bearer <jwt_or_api_key>
Content-Type: application/json

{
  "model": "openai/dall-e-3",
  "prompt": "A cat wearing a top hat, oil painting style",
  "n": 1,
  "size": "1024x1024",
  "quality": "hd",
  "style": "vivid",
  "response_format": "url"
}
```

- `model` (required) — format: `{alias}/{model_id}` e.g. `openai/dall-e-3`
- `prompt` (required) — text description of the image to generate
- `n` (optional) — number of images to generate (default: 1)
- `size` (optional) — image dimensions: `1024x1024`, `1024x1792`, `1792x1024`, `1024x1536`, `1536x1024`
- `quality` (optional) — `standard` or `hd` (OpenAI-specific)
- `style` (optional) — `vivid` or `natural` (OpenAI), or style preset (Stability AI)
- `response_format` (optional) — `url` (default) or `b64_json`
- `output_format` (optional) — `png`, `jpeg`, `webp` (for binary output mode)

**Response (OpenAI format):**
```json
{
  "created": 1716500000,
  "data": [
    {
      "url": "https://..."
    }
  ]
}
```

Or with base64:
```json
{
  "created": 1716500000,
  "data": [
    {
      "b64_json": "iVBORw0KGgo..."
    }
  ]
}
```

---

## Phase 1 — Backend: Image Provider Adapters

**New file:** `backend/app/services/image_adapters.py`

### 1.1 Shared Utilities

```python
import time

POLL_INTERVAL_S = 1.5
POLL_TIMEOUT_S = 120

def now_epoch() -> int:
    return int(time.time())

SIZE_TO_ASPECT_RATIO = {
    "1024x1024": "1:1",
    "1024x1792": "9:16",
    "1792x1024": "16:9",
    "1024x1536": "2:3",
    "1536x1024": "3:2",
}

def size_to_aspect_ratio(size: str) -> str:
    return SIZE_TO_ASPECT_RATIO.get(size, "1:1")
```

### 1.2 OpenAI-Compatible Adapter

```python
async def image_openai_compatible(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    model: str,
    prompt: str,
    n: int = 1,
    size: str = "1024x1024",
    quality: str = None,
    style: str = None,
    response_format: str = None,
) -> dict:
    """Standard OpenAI-compatible image generation."""
    body = {"model": model, "prompt": prompt, "n": n, "size": size}
    if quality:
        body["quality"] = quality
    if style:
        body["style"] = style
    if response_format:
        body["response_format"] = response_format
    
    resp = await client.post(f"{base_url}/images/generations", json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()
```

Used by: openai, openrouter, minimax, siliconflow, recraft.

### 1.3 Fal.ai Adapter (Async Polling)

```python
async def image_fal_ai(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    prompt: str,
    n: int = 1,
    size: str = "1024x1024",
) -> dict:
    """Fal.ai — async submit + poll for result."""
    import asyncio
    
    headers = {"Content-Type": "application/json", "Authorization": f"Key {api_key}"}
    body = {"prompt": prompt, "num_images": n}
    if size:
        body["image_size"] = size_to_aspect_ratio(size)
    
    # Submit
    resp = await client.post(f"https://queue.fal.run/{model}", json=body, headers=headers)
    resp.raise_for_status()
    submit_data = resp.json()
    status_url = submit_data["status_url"]
    response_url = submit_data["response_url"]
    
    # Poll
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL_S)
        status_resp = await client.get(status_url, headers=headers)
        status_resp.raise_for_status()
        status = status_resp.json()
        
        if status["status"] == "COMPLETED":
            result_resp = await client.get(response_url, headers=headers)
            result_resp.raise_for_status()
            result = result_resp.json()
            images = result.get("images", [])
            if not images and "image" in result:
                images = [result["image"]]
            return {"created": now_epoch(), "data": [{"url": img.get("url", img) if isinstance(img, dict) else img} for img in images]}
        
        if status["status"] == "FAILED":
            raise Exception(status.get("error", "Fal generation failed"))
    
    raise Exception("Fal.ai polling timeout after 120s")
```

### 1.4 Stability AI Adapter

```python
async def image_stability_ai(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    prompt: str,
    size: str = "1024x1024",
    style: str = None,
    output_format: str = "png",
) -> dict:
    """Stability AI v2 — sync, returns { image: "<b64>" }."""
    # Map model to endpoint segment
    if "ultra" in model:
        endpoint = "ultra"
    elif "sd3" in model:
        endpoint = "sd3"
    else:
        endpoint = "core"
    
    url = f"https://api.stability.ai/v2beta/stable-image/generate/{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    body = {"prompt": prompt, "output_format": output_format}
    if size:
        body["aspect_ratio"] = size_to_aspect_ratio(size)
    if style:
        body["style_preset"] = style
    if "sd3" in model:
        body["model"] = model
    
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    if "image" in data:
        return {"created": now_epoch(), "data": [{"b64_json": data["image"]}]}
    return {"created": now_epoch(), "data": []}
```

### 1.5 Gemini Adapter

```python
async def image_gemini(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    prompt: str,
) -> dict:
    """Gemini image generation via generateContent with IMAGE modality."""
    model_id = model.replace("models/", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    
    resp = await client.post(url, json=body)
    resp.raise_for_status()
    data = resp.json()
    
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    images = [{"b64_json": p["inlineData"]["data"]} for p in parts if p.get("inlineData", {}).get("data")]
    
    if not images:
        images = [{"b64_json": "", "revised_prompt": prompt}]
    
    return {"created": now_epoch(), "data": images}
```

### 1.6 HuggingFace Adapter

```python
async def image_huggingface(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    prompt: str,
) -> dict:
    """HuggingFace Inference API — returns raw binary image."""
    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"inputs": prompt}
    
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()
    
    # Response is raw image bytes → convert to base64
    import base64
    b64 = base64.b64encode(resp.content).decode()
    return {"created": now_epoch(), "data": [{"b64_json": b64}]}
```

### 1.7 Cloudflare AI Adapter

```python
async def image_cloudflare_ai(
    client: httpx.AsyncClient,
    api_key: str,
    account_id: str,
    model: str,
    prompt: str,
    size: str = "1024x1024",
) -> dict:
    """Cloudflare Workers AI image generation."""
    import base64
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Some Cloudflare models require multipart form data
    multipart_models = {
        "@cf/black-forest-labs/flux-2-dev",
        "@cf/black-forest-labs/flux-2-klein-4b",
        "@cf/black-forest-labs/flux-2-klein-9b",
    }
    
    width, height = 1024, 1024
    if size and "x" in size:
        parts = size.split("x")
        width, height = int(parts[0]), int(parts[1])
    
    if model in multipart_models:
        # Multipart form data
        import io
        form_data = {"prompt": prompt, "width": str(width), "height": str(height)}
        resp = await client.post(url, headers=headers, data=form_data)
    else:
        body = {"prompt": prompt, "width": width, "height": height}
        resp = await client.post(url, json=body, headers=headers)
    
    resp.raise_for_status()
    
    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type:
        data = resp.json()
        img = data.get("result", {}).get("image", "")
        if img:
            return {"created": now_epoch(), "data": [{"b64_json": img}]}
    else:
        # Binary response
        b64 = base64.b64encode(resp.content).decode()
        return {"created": now_epoch(), "data": [{"b64_json": b64}]}
    
    return {"created": now_epoch(), "data": []}
```

### 1.8 NanoBanana Adapter (Async Polling)

```python
async def image_nanobanana(
    client: httpx.AsyncClient,
    api_key: str,
    prompt: str,
    n: int = 1,
    size: str = "1024x1024",
    image: str = None,
) -> dict:
    """NanoBanana — async submit + poll for result."""
    import asyncio
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    
    is_edit = bool(image)
    body = {
        "prompt": prompt,
        "type": "IMAGETOIAMGE" if is_edit else "TEXTTOIAMGE",
        "numImages": n,
        "image_size": size_to_aspect_ratio(size),
        "callBackUrl": "https://localhost/callback",  # dummy, we poll instead
    }
    if is_edit:
        body["imageUrls"] = [image]
    
    # Submit
    resp = await client.post(
        "https://api.nanobananaapi.ai/api/v1/nanobanana/generate",
        json=body, headers=headers,
    )
    resp.raise_for_status()
    submit_data = resp.json()
    
    if submit_data.get("code") != 200:
        raise Exception(submit_data.get("msg", "NanoBanana submit failed"))
    
    task_id = submit_data.get("data", {}).get("taskId")
    if not task_id:
        raise Exception("NanoBanana: no taskId returned")
    
    # Poll
    poll_url = f"https://api.nanobananaapi.ai/api/v1/nanobanana/record-info?taskId={task_id}"
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL_S)
        poll_resp = await client.get(poll_url, headers=headers)
        poll_resp.raise_for_status()
        result = poll_resp.json()
        
        flag = result.get("data", {}).get("successFlag")
        if flag == 1:
            # Success
            img_url = (result.get("data", {}).get("response", {}).get("resultImageUrl")
                       or result.get("data", {}).get("response", {}).get("originImageUrl"))
            if img_url:
                return {"created": now_epoch(), "data": [{"url": img_url, "revised_prompt": prompt}]}
            return {"created": now_epoch(), "data": []}
        if flag in (2, 3):
            raise Exception(result.get("data", {}).get("errorMessage", "NanoBanana generation failed"))
    
    raise Exception("NanoBanana polling timeout after 120s")
```

### 1.9 Codex Adapter (SSE Streaming — Most Complex)

```python
async def image_codex(
    client: httpx.AsyncClient,
    api_key: str,
    id_token: str,
    prompt: str,
    model: str = "gpt-4o",
    image_refs: list[str] = None,
) -> dict:
    """Codex (ChatGPT) image generation via Responses API + SSE stream."""
    import base64
    import uuid
    
    # Strip -image suffix if present
    if model.endswith("-image"):
        model = model[:-6]
    
    url = "https://chatgpt.com/backend-api/codex/responses"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "codex-imagen/0.2.6",
    }
    
    # Build content with optional image references
    content = []
    if image_refs:
        for i, ref in enumerate(image_refs):
            content.append({"type": "input_text", "text": f"<image name=image{i+1}>"})
            content.append({"type": "input_image", "image_url": ref, "detail": "high"})
            content.append({"type": "input_text", "text": "</image>"})
    content.append({"type": "input_text", "text": prompt})
    
    body = {
        "model": model,
        "input": [{"role": "user", "content": content}],
        "stream": True,
    }
    
    # Stream SSE, accumulate base64 image chunks
    image_b64 = None
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        resp.raise_for_status()
        buffer = ""
        async for chunk in resp.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event_name = None
                data_str = ""
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str += line[5:].strip()
                
                if event_name == "response.output_image.delta" and data_str:
                    # Accumulate base64 chunks
                    try:
                        delta = json.loads(data_str)
                        if "delta" in delta:
                            image_b64 = (image_b64 or "") + delta["delta"]
                    except json.JSONDecodeError:
                        pass
                
                if event_name == "response.output_image.done" and data_str:
                    try:
                        done = json.loads(data_str)
                        if "data" in done:
                            image_b64 = done["data"]
                    except json.JSONDecodeError:
                        pass
    
    if image_b64:
        return {"created": now_epoch(), "data": [{"b64_json": image_b64}]}
    raise Exception("Codex returned no image data")
```

### 1.10 SD WebUI & ComfyUI Adapters (Local/NoAuth)

```python
async def image_sdwebui(
    client: httpx.AsyncClient,
    prompt: str,
    size: str = "1024x1024",
) -> dict:
    """Stable Diffusion WebUI — local server, no auth."""
    import base64
    
    width, height = 1024, 1024
    if size and "x" in size:
        w, h = size.split("x")
        width, height = int(w), int(h)
    
    body = {"prompt": prompt, "width": width, "height": height}
    resp = await client.post("http://localhost:7860/sdapi/v1/txt2img", json=body)
    resp.raise_for_status()
    data = resp.json()
    
    images = [{"b64_json": img} for img in data.get("images", [])]
    return {"created": now_epoch(), "data": images}


async def image_comfyui(
    client: httpx.AsyncClient,
    prompt: str,
    size: str = "1024x1024",
) -> dict:
    """ComfyUI — local server, no auth. Basic workflow submission."""
    body = {"prompt": {"3": {"inputs": {"text": prompt, "seed": 0}}}}
    resp = await client.post("http://localhost:8188/prompt", json=body)
    resp.raise_for_status()
    return {"created": now_epoch(), "data": []}
```

### 1.11 Dispatch Table

```python
IMAGE_ADAPTERS = {
    # OpenAI-compatible
    "openai": image_openai_compatible,
    "openrouter": image_openai_compatible,
    "minimax": image_openai_compatible,
    "siliconflow": image_openai_compatible,
    # Provider-specific
    "fal-ai": image_fal_ai,
    "stability-ai": image_stability_ai,
    "gemini": image_gemini,
    "huggingface": image_huggingface,
    "cloudflare-ai": image_cloudflare_ai,
    "nanobanana": image_nanobanana,
    "codex": image_codex,
    # Local/noAuth
    "sdwebui": image_sdwebui,
    "comfyui": image_comfyui,
}

def get_image_adapter(provider: str):
    return IMAGE_ADAPTERS.get(provider)
```

---

## Phase 2 — Backend: URL Builder for Image Endpoints

Most providers use `{base_url}/images/generations` but some have custom URLs.
Add a helper in `services/proxy.py`:

```python
def _build_image_url(provider: str, base_url: str, model: str, data: dict = None) -> str:
    """Build upstream image generation URL per provider."""
    base = base_url.rstrip("/")
    
    if provider == "fal-ai":
        return f"https://queue.fal.run/{model}"
    elif provider == "stability-ai":
        if "ultra" in model:
            return f"{base}/stable-image/generate/ultra"
        elif "sd3" in model:
            return f"{base}/stable-image/generate/sd3"
        return f"{base}/stable-image/generate/core"
    elif provider == "gemini":
        model_id = model.replace("models/", "")
        return f"{base}/models/{model_id}:generateContent"
    elif provider == "huggingface":
        return f"{base}/{model}"
    elif provider == "cloudflare-ai":
        account_id = (data or {}).get("accountId", "")
        return f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    elif provider == "nanobanana":
        return "https://api.nanobananaapi.ai/api/v1/nanobanana/generate"
    elif provider == "codex":
        return "https://chatgpt.com/backend-api/codex/responses"
    else:
        return f"{base}/images/generations"
```

---

## Phase 3 — Backend: Add `/v1/images/generations` Route

**File:** `backend/app/routers/v1_proxy.py`

```python
@router.post("/images/generations")
async def images_generations(
    request: Request,
    response_format: str = Query(None),
    db: AsyncSession = Depends(get_db),
    api_key_info=Depends(validate_api_key),
):
    """OpenAI-compatible image generation proxy."""
    from app.services.image_adapters import get_image_adapter
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    model_str = body.get("model")
    prompt = body.get("prompt")
    
    if not model_str:
        raise HTTPException(status_code=400, detail="Missing required field: model")
    if not prompt:
        raise HTTPException(status_code=400, detail="Missing required field: prompt")
    
    # Parse provider from model string
    if "/" not in model_str:
        raise HTTPException(status_code=400, detail="Model must be in provider/model format")
    
    provider_name, model_id = model_str.split("/", 1)
    provider_id = _resolve_provider_alias(provider_name)
    
    # Check adapter exists
    adapter = get_image_adapter(provider_id)
    if not adapter:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_id}' does not support image generation")
    
    # DB lookup: find active connection
    result = await db.execute(
        select(ProviderConnection)
        .where(ProviderConnection.provider == provider_id, ProviderConnection.is_active == True)
        .order_by(ProviderConnection.priority)
    )
    connections = result.scalars().all()
    
    if not connections and provider_id not in ("sdwebui", "comfyui"):
        raise HTTPException(status_code=503, detail=f"No connection for provider: {provider_id}")
    
    # Combo expansion (same pattern as chat)
    targets = await resolve_model_to_targets(db, model_str, stream=False)
    strategy, sticky_limit = await get_combo_strategy(db)
    targets = _get_rotated_targets(targets, model_str, strategy, sticky_limit)
    
    last_error = None
    for conn in (connections or [None]):
        data = json.loads(conn.data) if conn and conn.data else {}
        api_key = data.get("apiKey", "")
        base_url = data.get("baseUrl") or PROVIDER_DEFAULTS.get(provider_id, {}).get("baseUrl", "")
        
        try:
            cfg = PROVIDER_CONFIGS.get(provider_id, {})
            headers = {"Content-Type": "application/json"}
            if api_key:
                auth_header = cfg.get("auth_header", "Authorization")
                auth_prefix = cfg.get("auth_prefix", "Bearer ")
                headers[auth_header] = f"{auth_prefix}{api_key}"
            
            result = await adapter(
                client=httpx.AsyncClient(timeout=180.0),
                base_url=base_url,
                headers=headers,
                api_key=api_key,
                model=model_id,
                prompt=prompt,
                n=body.get("n", 1),
                size=body.get("size", "1024x1024"),
                quality=body.get("quality"),
                style=body.get("style"),
                response_format=body.get("response_format"),
            )
            
            # Binary output mode
            if response_format == "binary":
                first = result.get("data", [{}])[0]
                b64 = first.get("b64_json", "")
                if not b64 and first.get("url"):
                    # Fetch URL → base64
                    img_resp = await httpx.AsyncClient().get(first["url"])
                    import base64
                    b64 = base64.b64encode(img_resp.content).decode()
                
                if b64:
                    import base64
                    img_bytes = base64.b64decode(b64)
                    fmt = body.get("output_format", "png")
                    mime = {"jpeg": "image/jpeg", "jpg": "image/jpeg", "webp": "image/webp"}.get(fmt, "image/png")
                    return Response(content=img_bytes, media_type=mime)
            
            return JSONResponse(content=result)
        
        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if e.response.status_code < 500:
                return JSONResponse(status_code=e.response.status_code, content={"error": {"message": e.response.text[:500]}})
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)}
            continue
    
    error_msg = last_error.get("detail", "All providers failed") if last_error else "No targets"
    error_status = last_error.get("status", 502) if last_error else 502
    return JSONResponse(status_code=error_status, content={"error": {"message": error_msg}})
```

---

## Phase 4 — Frontend: No Changes Required

The `/v1/images/generations` endpoint is a pure API endpoint. No UI changes
needed. MediaProvidersPage already shows image providers.

---

## Phase 5 — Testing

### 5.1 Manual curl tests

```bash
TOKEN=$(curl -s -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password": "123456"}' | jq -r '.access_token')
```

**Test 1 — OpenAI DALL·E (happy path, URL response):**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/dall-e-3", "prompt": "A cat wearing a top hat", "size": "1024x1024"}' \
  | jq '{created, data_count: (.data | length), has_url: (.data[0].url != null)}'
```
Expected: `data_count: 1`, `has_url: true`.

**Test 2 — OpenAI DALL·E (base64 response):**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/dall-e-3", "prompt": "A sunset over mountains", "response_format": "b64_json"}' \
  | jq '{created, data_count: (.data | length), b64_len: (.data[0].b64_json | length)}'
```
Expected: `b64_len > 1000`.

**Test 3 — Gemini image generation:**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini/gemini-2.0-flash-exp", "prompt": "A cute robot"}' \
  | jq '{created, data_count: (.data | length)}'
```

**Test 4 — Stability AI:**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "stability-ai/stable-diffusion-xl-1024-v1-0", "prompt": "A futuristic city"}' \
  | jq '{created, data_count: (.data | length)}'
```

**Test 5 — Missing model (400):**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cat"}' | jq .
```
Expected: `400` with `"Missing required field: model"`.

**Test 6 — Missing prompt (400):**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/dall-e-3"}' | jq .
```
Expected: `400` with `"Missing required field: prompt"`.

**Test 7 — No connection (503):**
```bash
curl -s -X POST http://localhost:9000/v1/images/generations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "nonexistent/some-model", "prompt": "A cat"}' | jq .
```
Expected: `503` or `400`.

**Test 8 — Binary output mode:**
```bash
curl -s -X POST "http://localhost:9000/v1/images/generations?response_format=binary" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/dall-e-3", "prompt": "A cat"}' \
  --output test_image.png -w "HTTP %{http_code} Content-Type: %{content_type}\n"
```
Expected: `Content-Type: image/png`.

### 5.2 Regression check

```bash
curl -s -X POST http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}]}' \
  | jq '.choices[0].message.content'
```

---

## Phase 6 — Report

1. **`docs/porting-status.md`** — Move `POST /v1/images/generations` to "Fully Ported".
2. **`docs/plans/v1-proxy-endpoints.md`** — Mark endpoint 5 as ✅.
3. **`docs/plans/v1-images-generations.md`** (this file) — Update status to `Done`.

---

## Known Limitations & Follow-ups

| Item | Notes |
|------|-------|
| Codex SSE streaming | Most complex adapter. Requires OAuth token (not API key). Streams base64 chunks. If Codex changes their API, this breaks. |
| Fal.ai async polling | 120s timeout. Large images may take longer. |
| NanoBanana async polling | Same 120s timeout. Requires dummy callback URL. |
| Cloudflare multipart | Some models require multipart form data instead of JSON. Auto-detected by model name. |
| Gemini image models | Only works with models that support IMAGE modality (e.g. gemini-2.0-flash-exp). |
| SD WebUI / ComfyUI | Local services. Won't work in Docker unless port is exposed. |
| Combo expansion | The original supports combos for image generation. This implementation does basic combo expansion via `resolve_model_to_targets()`. |
| Binary output mode | `?response_format=binary` returns raw image bytes. Used by MediaProviderDetailPage for preview. |
| image_refs (Codex) | Codex supports image editing by passing reference images. Not exposed in the API yet. |
| Streaming SSE to client | The original can stream Codex SSE events directly to the client. Not implemented in Phase 1 — all responses are non-streaming. |

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/services/image_adapters.py` | NEW — 14 image provider adapters, dispatch table, shared utils |
| `backend/app/services/proxy.py` | Add `_build_image_url()` helper |
| `backend/app/routers/v1_proxy.py` | Add `POST /v1/images/generations` handler |
| `docs/porting-status.md` | Move images endpoint to ported table |
| `docs/plans/v1-proxy-endpoints.md` | Mark endpoint 5 done |
| `docs/plans/v1-images-generations.md` | Update status to Done |

No DB migrations. No frontend changes. No new pip dependencies.

---

## Complexity Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Route handler | Medium | JSON parsing, provider dispatch, combo expansion |
| OpenAI-compatible adapter | Low | Standard body format, well-documented |
| Fal.ai adapter | Medium | Async polling, status_url/response_url |
| Stability AI adapter | Medium | Model-to-endpoint mapping, aspect ratio |
| Gemini adapter | Medium | generateContent API, inline base64 extraction |
| HuggingFace adapter | Low | Binary response → base64 conversion |
| Cloudflare AI adapter | Medium | Account ID in URL, multipart for some models |
| NanoBanana adapter | Medium | Async polling, Chinese API error format |
| Codex adapter | High | SSE stream parsing, OAuth token, base64 accumulation |
| SD WebUI adapter | Low | Simple local API |
| ComfyUI adapter | Low | Simple local API |
| Binary output mode | Low | Base64 decode → raw bytes with Content-Type |

**Overall:** High complexity — the most adapter-heavy endpoint. The route handler
is straightforward, but 14 adapters with different APIs, 2 async polling patterns,
and 1 SSE streaming pattern make this the hardest endpoint to implement.

**Recommended implementation order:**
1. OpenAI-compatible (openai, openrouter, minimax, siliconflow) — Group A
2. HuggingFace (binary → base64, simple)
3. Stability AI (sync, custom URL)
4. Gemini (generateContent, inline base64)
5. Cloudflare AI (account ID, multipart detection)
6. Fal.ai (async polling)
7. NanoBanana (async polling, similar to Fal.ai)
8. SD WebUI + ComfyUI (local, trivial)
9. Codex (SSE streaming — most complex, do last)
