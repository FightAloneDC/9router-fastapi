"""
STT (Speech-to-Text) provider adapters for /v1/audio/transcriptions.

Each adapter takes the audio bytes + metadata and returns a dict shaped like
OpenAI's response: ``{"text": "..."}``. Verbose JSON (``segments``, etc.) is
passed through for OpenAI-compatible providers when the client requests
``response_format=verbose_json``.

Design mirrors ``tts_adapters.py``:
- kwargs-only adapter signatures with ``**_kwargs`` catch-all so the route
  handler can pass extra params without breaking other adapters
- adapters raise ``httpx.HTTPStatusError`` on upstream HTTP errors (route
  handler decides about fallback) or ``ValueError`` for adapter-level
  validation failures (e.g. missing model, malformed key)
- some adapters embed their own URL (gemini, assemblyai) → flagged in
  ``_FIXED_URL_STT_PROVIDERS`` so the route handler skips the base_url check
"""
from __future__ import annotations

import asyncio
import base64
import io
from typing import Any, Awaitable, Callable

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# MIME helper
# ─────────────────────────────────────────────────────────────────────────────

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
    """Resolve audio MIME type from filename extension or declared Content-Type.

    Prefers the declared Content-Type if it is an ``audio/*`` value, otherwise
    falls back to the filename extension. Returns ``application/octet-stream``
    as a safe default if nothing matches.
    """
    if declared_type and declared_type.startswith("audio/"):
        return declared_type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return AUDIO_MIME_MAP.get(ext, "application/octet-stream")


# ─────────────────────────────────────────────────────────────────────────────
# Adapter type
# ─────────────────────────────────────────────────────────────────────────────

# Each adapter returns a dict (OpenAI-shaped: at minimum has "text" key, may
# include other keys like "language", "duration", "segments" for verbose).
STTAdapter = Callable[..., Awaitable[dict[str, Any]]]


# ─────────────────────────────────────────────────────────────────────────────
# 1. OpenAI Whisper-compatible (openai, groq, azure)
# ─────────────────────────────────────────────────────────────────────────────


async def stt_openai_compatible(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    language: str | None = None,
    prompt: str | None = None,
    response_format: str | None = None,
    temperature: float | None = None,
    auth_header: str = "Authorization",
    auth_prefix: str = "Bearer ",
    extra_url: str | None = None,
    **_kwargs,
) -> dict[str, Any]:
    """Standard Whisper-compatible multipart transcription.

    POSTs ``file`` + ``model`` (+ optional language/prompt/response_format/temperature)
    as multipart form data. Response is OpenAI-shaped JSON.

    ``extra_url`` overrides the default ``{base_url}/audio/transcriptions``
    path (used by Azure which embeds the deployment name).
    """
    if not model:
        raise ValueError("STT model is required (provider/model format)")

    url = extra_url or f"{base_url.rstrip('/')}/audio/transcriptions"
    headers = {auth_header: f"{auth_prefix}{api_key}"} if api_key else {}

    files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
    data: dict[str, str] = {"model": model}
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    if response_format:
        data["response_format"] = response_format
    if temperature is not None:
        data["temperature"] = str(temperature)

    resp = await client.post(url, headers=headers, files=files, data=data)
    resp.raise_for_status()

    # If response_format is text/srt/vtt, response is plain text not JSON.
    if response_format in ("text", "srt", "vtt"):
        return {"text": resp.text}

    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Deepgram (raw binary + query params)
# ─────────────────────────────────────────────────────────────────────────────


async def stt_deepgram(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str | None = None,
    **_kwargs,
) -> dict[str, Any]:
    """Deepgram STT — raw binary POST with model as query param.

    Uses ``Token`` auth prefix (NOT Bearer). Model passed as ``?model=`` query
    param. When ``language`` omitted, requests language auto-detection.
    """
    if not model:
        raise ValueError("Deepgram requires a model (e.g. 'nova-3')")
    if not api_key:
        raise ValueError("Deepgram requires an API key")

    base = base_url.rstrip("/") if base_url else "https://api.deepgram.com/v1/listen"
    params = [f"model={model}", "smart_format=true", "punctuate=true"]
    if language:
        params.append(f"language={language}")
    else:
        params.append("detect_language=true")
    url = f"{base}?{'&'.join(params)}"

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": content_type,
    }

    resp = await client.post(url, content=file_bytes, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    transcript = (
        data.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("transcript", "")
    )
    detected_lang = data.get("results", {}).get("channels", [{}])[0].get("detected_language")
    out: dict[str, Any] = {"text": transcript}
    if detected_lang:
        out["language"] = detected_lang
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 3. Gemini STT (generateContent with inline audio)
# ─────────────────────────────────────────────────────────────────────────────


async def stt_gemini(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str | None = None,
    prompt: str | None = None,
    **_kwargs,
) -> dict[str, Any]:
    """Gemini STT — generateContent with audio as base64 inline_data.

    Uses the Gemini chat API repurposed for transcription via a prompt instruction.
    URL is hardcoded (ignores base_url). Auth via ``?key=`` query param.
    """
    if not model:
        raise ValueError("Gemini STT requires a model")
    if not api_key:
        raise ValueError("Gemini requires an API key")

    b64_audio = base64.b64encode(file_bytes).decode("ascii")

    instruction = prompt or (
        "Generate a transcript of the speech. "
        "Return only the transcribed text, no commentary."
    )
    if language:
        instruction += f" Language: {language}."

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": instruction},
                    {"inline_data": {"mime_type": content_type, "data": b64_audio}},
                ]
            }
        ]
    }

    resp = await client.post(url, json=body)
    resp.raise_for_status()

    data = resp.json()
    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    text = "".join(p.get("text", "") for p in parts if "text" in p)
    return {"text": text.strip()}


# ─────────────────────────────────────────────────────────────────────────────
# 4. AssemblyAI (3-step async upload/submit/poll)
# ─────────────────────────────────────────────────────────────────────────────

_ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"


async def stt_assemblyai(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    language: str | None = None,
    max_poll_seconds: int = 120,
    poll_interval: float = 2.0,
    **_kwargs,
) -> dict[str, Any]:
    """AssemblyAI STT — 3-step async flow.

    1. Upload audio to ``/v2/upload`` → get ``upload_url``
    2. Submit transcription job to ``/v2/transcript`` with ``audio_url``
    3. Poll ``/v2/transcript/{id}`` every ``poll_interval`` seconds until
       status is ``completed`` or ``error``, max ``max_poll_seconds`` total

    URL is hardcoded (ignores base_url).
    """
    if not api_key:
        raise ValueError("AssemblyAI requires an API key")

    headers = {"Authorization": api_key}  # AssemblyAI uses raw key, NO "Bearer " prefix

    # Step 1: Upload
    upload_resp = await client.post(
        f"{_ASSEMBLYAI_BASE}/upload",
        content=file_bytes,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    upload_resp.raise_for_status()
    upload_url = upload_resp.json().get("upload_url")
    if not upload_url:
        raise ValueError("AssemblyAI upload returned no upload_url")

    # Step 2: Submit transcription job
    submit_body: dict[str, Any] = {"audio_url": upload_url}
    if model:
        # AssemblyAI deprecated `speech_model` (singular) in 2025 — use `speech_models` (plural array).
        # Valid values: "best", "nano", "universal", "slam-1".
        submit_body["speech_models"] = [model]
    if language:
        submit_body["language_code"] = language
    else:
        submit_body["language_detection"] = True

    submit_resp = await client.post(
        f"{_ASSEMBLYAI_BASE}/transcript",
        json=submit_body,
        headers={**headers, "Content-Type": "application/json"},
    )
    submit_resp.raise_for_status()
    transcript_id = submit_resp.json().get("id")
    if not transcript_id:
        raise ValueError("AssemblyAI submit returned no transcript id")

    # Step 3: Poll
    poll_url = f"{_ASSEMBLYAI_BASE}/transcript/{transcript_id}"
    max_iters = max(1, int(max_poll_seconds / poll_interval))
    for _ in range(max_iters):
        await asyncio.sleep(poll_interval)
        poll_resp = await client.get(poll_url, headers=headers)
        if poll_resp.status_code != 200:
            continue
        result = poll_resp.json()
        st = result.get("status")
        if st == "completed":
            out: dict[str, Any] = {"text": result.get("text", "")}
            lang = result.get("language_code")
            if lang:
                out["language"] = lang
            return out
        if st == "error":
            raise ValueError(
                f"AssemblyAI transcription failed: {result.get('error', 'unknown error')}"
            )

    raise ValueError(f"AssemblyAI transcription timeout after {max_poll_seconds}s")


# ─────────────────────────────────────────────────────────────────────────────
# 5. HuggingFace (raw binary to model-specific URL)
# ─────────────────────────────────────────────────────────────────────────────


async def stt_huggingface(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    content_type: str,
    **_kwargs,
) -> dict[str, Any]:
    """HuggingFace ASR — raw binary POST to ``{base_url}/{model}``.

    Model IDs typically contain a ``/`` (e.g. ``openai/whisper-large-v3``).
    We reject ``..`` to prevent path traversal but allow normal slashes.
    """
    if not model:
        raise ValueError("HuggingFace requires a model id")
    if ".." in model.split("/"):
        raise ValueError("Invalid HuggingFace model id (contains '..')")

    base = base_url.rstrip("/") if base_url else "https://api-inference.huggingface.co/models"
    url = f"{base}/{model}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": content_type,
    }

    resp = await client.post(url, content=file_bytes, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    # HF returns either {"text": "..."} or sometimes a list
    if isinstance(data, dict) and "text" in data:
        return {"text": data["text"]}
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return {"text": data[0].get("text", "")}
    return {"text": str(data)}


# ─────────────────────────────────────────────────────────────────────────────
# 6. NVIDIA NIM (multipart, OpenAI-style)
# ─────────────────────────────────────────────────────────────────────────────


async def stt_nvidia(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    model: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    language: str | None = None,
    **_kwargs,
) -> dict[str, Any]:
    """NVIDIA NIM STT — multipart form data with simple response normalization."""
    if not model:
        raise ValueError("NVIDIA STT requires a model")
    if not api_key:
        raise ValueError("NVIDIA STT requires an API key")

    url = (
        base_url.rstrip("/")
        if base_url
        else "https://integrate.api.nvidia.com/v1/audio/transcriptions"
    )

    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, io.BytesIO(file_bytes), content_type)}
    data: dict[str, str] = {"model": model}
    if language:
        data["language"] = language

    resp = await client.post(url, headers=headers, files=files, data=data)
    resp.raise_for_status()

    result = resp.json()
    return {"text": result.get("text") or result.get("transcript", "")}


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table
# ─────────────────────────────────────────────────────────────────────────────


STT_ADAPTERS: dict[str, STTAdapter] = {
    # OpenAI Whisper-compatible (default multipart path)
    "openai": stt_openai_compatible,
    "groq": stt_openai_compatible,
    "azure": stt_openai_compatible,
    # Provider-specific
    "deepgram": stt_deepgram,
    "gemini": stt_gemini,
    "assemblyai": stt_assemblyai,
    "huggingface": stt_huggingface,
    # NVIDIA NIM: not supported. The original 9router providers.js does NOT
    # declare `stt` in nvidia's serviceKinds, and there is no public
    # OpenAI-compatible /v1/audio/transcriptions endpoint at
    # integrate.api.nvidia.com (verified: returns "404 page not found").
    # Riva ASR exists but uses gRPC, not REST. Kept the adapter function
    # available for future Riva integration via a different URL/auth scheme.
}


# Providers whose adapter embeds its own URL — don't fail when base_url is empty
_FIXED_URL_STT_PROVIDERS: set[str] = {"gemini", "assemblyai", "deepgram", "huggingface"}


def get_stt_adapter(provider: str) -> STTAdapter | None:
    """Return the adapter for ``provider`` or None if unsupported."""
    return STT_ADAPTERS.get(provider)
