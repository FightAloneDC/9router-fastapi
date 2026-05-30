"""TTS provider adapters for /v1/audio/speech endpoint.

Each adapter takes a normalized set of args and returns ``(audio_bytes, content_type)``.
The dispatch table at the bottom maps provider IDs to adapter functions.

**No default models or voices**: callers must supply both ``tts_model`` and
``voice`` explicitly. The frontend is expected to fetch the model list per
provider (e.g. via ``/api/providers/{id}/models``) and let the user pick. This
matches the rest of 9Router's "no hardcoded defaults — fetch from provider"
convention used by chat completions and embeddings.

Iterasi 1 (2026-05-23): Group A only — OpenAI-compatible providers.
  - openai, siliconflow, hyperbolic
Iterasi 2 (2026-05-23): Group B-1 — gemini, elevenlabs, minimax, openrouter.
Iterasi 3 (2026-05-23): Group B-2 — deepgram, nvidia, huggingface, inworld, cartesia, playht.
Group C — free/local: edge-tts (no API key needed).
Deferred: coqui, tortoise, google-tts, local-device (need local services).
"""

from __future__ import annotations

import struct
from typing import Awaitable, Callable

import httpx

# ─────────────────────────────────────────────────────────────────────────────
# PCM → WAV utility (used by gemini in Iterasi 2)
# ─────────────────────────────────────────────────────────────────────────────


def pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    bits: int = 16,
) -> bytes:
    """Wrap raw PCM audio data in a WAV (RIFF) header.

    Args:
        pcm_data: Raw PCM samples (little-endian).
        sample_rate: Samples per second (Hz). Gemini TTS = 24000.
        channels: 1 (mono) or 2 (stereo).
        bits: Bits per sample (typically 16).

    Returns:
        Complete WAV file as bytes (header + PCM payload).
    """
    byte_rate = sample_rate * channels * bits // 8
    block_align = channels * bits // 8
    data_size = len(pcm_data)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size
        1,  # audio format (1 = PCM)
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b"data",
        data_size,
    )
    return header + pcm_data


# ─────────────────────────────────────────────────────────────────────────────
# Group A: OpenAI-compatible adapters
# ─────────────────────────────────────────────────────────────────────────────


async def tts_openai_compatible(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    speed: float | None = None,
    extra_headers: dict | None = None,
    **_kwargs,
) -> tuple[bytes, str]:
    """OpenAI-compatible /audio/speech endpoint.

    Used by: openai, siliconflow.
    Returns binary audio bytes with the requested response_format.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    body: dict = {
        "model": tts_model,
        "voice": voice,
        "input": input_text,
        "response_format": response_format,
    }
    if speed is not None:
        body["speed"] = speed

    url = f"{base_url.rstrip('/')}/audio/speech"
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", _format_to_mime(response_format))
    return resp.content, content_type


async def tts_hyperbolic(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """Hyperbolic /audio/generation — returns ``{"audio": <base64>}`` JSON.

    Differs from OpenAI-compat: body uses ``text`` (not ``input``), response is
    base64 JSON instead of binary stream. The ``voice`` field is mapped to
    Hyperbolic's ``language`` parameter (e.g. ``EN-US``, ``ZH``, ``JA``).
    """
    import base64

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": tts_model,
        "text": input_text,
        "language": voice,
        "speaker": "EN-Default",
        "sdp_ratio": 0.5,
        "noise_scale": 0.6,
        "noise_scale_w": 0.8,
        "speed": 1.0,
    }
    url = f"{base_url.rstrip('/')}/audio/generation"
    resp = await client.post(url, json=body, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    audio_b64 = data.get("audio") or data.get("data", {}).get("audio")
    if not audio_b64:
        raise ValueError(f"Hyperbolic response missing audio field: {data!r}"[:300])

    return base64.b64decode(audio_b64), "audio/mpeg"


# ─────────────────────────────────────────────────────────────────────────────
# Group B: provider-specific adapters
# ─────────────────────────────────────────────────────────────────────────────


async def tts_gemini(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    language: str | None = None,
    **_kwargs,
) -> tuple[bytes, str]:
    """Google Gemini TTS — generateContent with AUDIO modality.

    Returns raw PCM L16 mono @ 24kHz inside ``candidates[0].content.parts[*].inlineData.data``
    (base64). We wrap it in a WAV container before returning to the caller.

    Notes:
      - ``base_url`` is **ignored**; Gemini has a fixed endpoint with the model
        ID embedded in the path and the API key as a query param.
      - ``language`` is an optional opt-in hint that gets baked into the prompt
        ("Say in {language}: ..."). If the user's input already has a colon-space
        ("Tone: ..."), no prefix is added (treats input as style-controlled prompt).
      - WAV output is fixed at 24kHz mono 16-bit signed PCM. ``response_format``
        is ignored — Gemini always returns PCM, we always return WAV.
    """
    import base64

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{tts_model}:generateContent?key={api_key}"
    )
    prompt = _build_gemini_prompt(input_text, language)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }
    resp = await client.post(url, json=body, headers={"Content-Type": "application/json"})
    if not resp.is_success:
        # Surface Gemini's structured error message when available
        try:
            err = resp.json()
            msg = err.get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise ValueError(msg or f"Gemini TTS failed: {resp.status_code}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        block = data.get("promptFeedback", {}).get("blockReason", "unknown")
        raise ValueError(f"Gemini TTS returned no candidates (blockReason: {block})")

    parts = candidates[0].get("content", {}).get("parts") or []
    b64 = None
    for p in parts:
        inline = p.get("inlineData") or p.get("inline_data")
        if inline and inline.get("data"):
            b64 = inline["data"]
            break

    if not b64:
        finish = candidates[0].get("finishReason", "unknown")
        raise ValueError(
            f"Gemini TTS returned no audio (finishReason: {finish}, "
            f"voice: {voice}, model: {tts_model})"
        )

    pcm = base64.b64decode(b64)
    wav = pcm_to_wav(pcm, sample_rate=24000, channels=1, bits=16)
    return wav, "audio/wav"


def _build_gemini_prompt(text: str, language: str | None) -> str:
    """Inject a TTS-mode prefix unless the user already supplied a style instruction.

    Gemini's generateContent endpoint is multimodal — without an explicit ``Say:``
    instruction it may interpret the text as a question and return a text reply
    in audio form. The colon-space heuristic preserves existing style prompts
    like ``"Whispering: hello world"``.
    """
    import re

    if re.search(r":\s", text):
        return text  # User already provided style instruction
    return f"Say in {language}: {text}" if language else f"Say: {text}"


async def tts_elevenlabs(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """ElevenLabs TTS — voice ID embedded in URL path.

    Endpoint: ``https://api.elevenlabs.io/v1/text-to-speech/{voice_id}``.
    Auth: ``xi-api-key`` header (NOT Bearer).
    Body: ``{text, model_id, voice_settings}``. Response: binary MP3.

    The ``base_url`` is fixed (api.elevenlabs.io) — adapter ignores any
    provider-level base_url override since ElevenLabs doesn't expose alternate
    regions or self-hosted endpoints.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": input_text,
        "model_id": tts_model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    resp = await client.post(url, json=body, headers=headers)
    if not resp.is_success:
        try:
            err = resp.json()
            msg = (err.get("detail") or {}).get("message") or err.get("detail") or ""
        except Exception:
            msg = ""
        raise ValueError(msg or f"ElevenLabs TTS failed: {resp.status_code}")

    audio = resp.content
    if len(audio) < 1024:
        raise ValueError("ElevenLabs TTS returned empty/truncated audio (< 1KB)")

    return audio, "audio/mpeg"


async def tts_minimax(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """MiniMax T2A HTTP — returns **hex-encoded** audio inside JSON.

    Body shape is unique:
      - ``voice_setting``: {voice_id, speed, vol, pitch}
      - ``audio_setting``: {sample_rate, bitrate, format, channel}
      - ``output_format``: "hex" (so we don't have to deal with binary streaming)

    Response: ``{ data: { audio: "<hex>" }, base_resp: { status_code, status_msg } }``.
    We decode hex → bytes and return as MP3.

    MiniMax's ``base_resp.status_code`` can be non-zero even when HTTP is 200 —
    must check both.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": tts_model,
        "text": input_text,
        "stream": False,
        "language_boost": "auto",
        "output_format": "hex",
        "voice_setting": {
            "voice_id": voice,
            "speed": 1,
            "vol": 1,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": response_format if response_format in {"mp3", "wav", "pcm", "flac"} else "mp3",
            "channel": 1,
        },
    }
    # MiniMax base_url is the full T2A endpoint (https://api.minimax.io/v1/t2a_v2 or
    # https://api.minimaxi.com/v1/t2a_v2 for the China region). No URL building.
    resp = await client.post(base_url, json=body, headers=headers)

    raw = resp.text
    data: dict = {}
    if raw:
        try:
            data = resp.json()
        except Exception:
            data = {}

    base_resp = data.get("base_resp") or data.get("baseResp") or {}
    status_code = int(base_resp.get("status_code", base_resp.get("statusCode", 0)) or 0)
    status_msg = (
        base_resp.get("status_msg")
        or base_resp.get("statusMsg")
        or data.get("message")
        or ""
    )

    if not resp.is_success:
        raise ValueError(status_msg or raw[:300] or f"MiniMax TTS error ({resp.status_code})")
    if status_code != 0:
        raise ValueError(status_msg or "MiniMax TTS upstream error")

    audio_hex = (data.get("data") or {}).get("audio") or ""
    if not audio_hex:
        raise ValueError("MiniMax TTS returned no audio")

    audio_hex = audio_hex.strip()
    if len(audio_hex) % 2 != 0 or not all(c in "0123456789abcdefABCDEF" for c in audio_hex):
        raise ValueError("MiniMax TTS returned invalid hex audio")

    audio_bytes = bytes.fromhex(audio_hex)
    fmt = (data.get("extra_info") or data.get("extraInfo") or {}).get("audio_format") or "mp3"
    return audio_bytes, _format_to_mime(fmt)


async def tts_openrouter(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "wav",
    **_kwargs,
) -> tuple[bytes, str]:
    """OpenRouter TTS — via chat completions w/ audio modality, SSE stream.

    OpenRouter pipes TTS through their chat endpoint with ``modalities=["text","audio"]``
    and streams base64 audio chunks via SSE. We accumulate ``delta.audio.data``
    fragments and concatenate them into the final base64 payload.

    The ``tts_model`` here is the *upstream* model ID (e.g. ``openai/gpt-4o-mini-tts``
    or ``google/gemini-2.5-flash-preview-tts``). OpenRouter handles the routing.

    Output format is fixed to WAV — that's what OpenRouter returns and the
    ``response_format`` body field controls the audio.format request param.
    """
    import base64

    url = "https://openrouter.ai/api/v1/chat/completions"
    fmt = response_format if response_format in {"wav", "mp3", "flac", "opus", "pcm16"} else "wav"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://9router.local",
        "X-Title": "9Router",
    }
    body = {
        "model": tts_model,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": fmt},
        "stream": True,
        "messages": [{"role": "user", "content": input_text}],
    }

    chunks: list[str] = []
    async with client.stream("POST", url, json=body, headers=headers) as resp:
        if not resp.is_success:
            # Drain the body so we can read the error
            await resp.aread()
            try:
                err = resp.json()
                msg = (err.get("error") or {}).get("message", "")
            except Exception:
                msg = ""
            raise ValueError(msg or f"OpenRouter TTS failed: {resp.status_code}")

        buffer = ""
        async for raw in resp.aiter_text():
            buffer += raw
            lines = buffer.split("\n")
            buffer = lines.pop()  # keep last partial line
            for line in lines:
                line = line.strip()
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                try:
                    import json as _json
                    payload = _json.loads(line[6:])
                except Exception:
                    continue
                choices = payload.get("choices") or []
                if not choices:
                    continue
                audio_data = (
                    (choices[0].get("delta") or {}).get("audio") or {}
                ).get("data")
                if audio_data:
                    chunks.append(audio_data)

    if not chunks:
        raise ValueError("OpenRouter TTS returned no audio data")

    joined_b64 = "".join(chunks)
    audio_bytes = base64.b64decode(joined_b64)
    return audio_bytes, _format_to_mime(fmt)


# ─────────────────────────────────────────────────────────────────────────────
# Group B-2 (Iterasi 3): simple binary providers
# ─────────────────────────────────────────────────────────────────────────────


async def tts_deepgram(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """Deepgram TTS — POST {base_url}?model={voice}, body {text}.

    - Auth: ``Token`` prefix (NOT Bearer).
    - Voice (e.g. ``aura-asteria-en``) is sent as the ``model`` query param —
      Deepgram conflates voice + model into one identifier. We accept the
      caller's ``voice`` here as the upstream model param; ``tts_model`` is
      ignored unless ``voice`` is empty (then we fall back to it).
    - Response is binary audio (default MP3). ``response_format`` not forwarded;
      Deepgram returns whatever its model produces.
    """
    upstream_model = voice or tts_model
    if not upstream_model:
        raise ValueError("Deepgram TTS requires a voice/model (e.g. 'aura-asteria-en')")

    # base_url is the full /speak endpoint; attach model as query param.
    sep = "&" if "?" in base_url else "?"
    url = f"{base_url}{sep}model={upstream_model}"

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    body = {"text": input_text}
    resp = await client.post(url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"Deepgram TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    audio = resp.content
    if not audio:
        raise ValueError("Deepgram TTS returned empty audio")
    # Deepgram defaults to MP3; honour Content-Type if present.
    content_type = resp.headers.get("content-type") or _format_to_mime("mp3")
    return audio, content_type


async def tts_nvidia(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "wav",
    **_kwargs,
) -> tuple[bytes, str]:
    """NVIDIA NIM TTS — POST {base_url} body {input:{text}, voice, model}.

    Base URL is fully-qualified (e.g. ``https://integrate.api.nvidia.com/v1/audio/speech``)
    — no path building. Auth: ``Bearer``. Response: binary WAV.
    """
    if not voice:
        raise ValueError("NVIDIA TTS requires a voice (e.g. 'English-US.Female-1')")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "input": {"text": input_text},
        "voice": voice,
    }
    if tts_model:
        body["model"] = tts_model
    resp = await client.post(base_url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"NVIDIA TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    audio = resp.content
    if not audio:
        raise ValueError("NVIDIA TTS returned empty audio")
    content_type = resp.headers.get("content-type") or _format_to_mime("wav")
    return audio, content_type


async def tts_huggingface(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "wav",
    **_kwargs,
) -> tuple[bytes, str]:
    """HuggingFace Inference TTS — POST {base_url}/{model_id} body {inputs: text}.

    Path includes the HF model ID (e.g. ``facebook/mms-tts-eng``). We sanitize
    against ``..`` traversal but otherwise pass through. ``voice`` is ignored
    — HF TTS models are voice-fixed.

    Default base_url for the JS reference is ``https://api-inference.huggingface.co/models``.
    """
    if not tts_model:
        raise ValueError("HuggingFace TTS requires a model (e.g. 'facebook/mms-tts-eng')")
    if ".." in tts_model:
        raise ValueError("Invalid HuggingFace model ID (path traversal)")

    url = f"{base_url.rstrip('/')}/{tts_model.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"inputs": input_text}
    resp = await client.post(url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"HuggingFace TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    audio = resp.content
    if not audio:
        raise ValueError("HuggingFace TTS returned empty audio")
    content_type = resp.headers.get("content-type") or _format_to_mime("wav")
    return audio, content_type


async def tts_inworld(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """Inworld TTS — POST {base_url} body {text, voiceId, modelId, audioConfig}.

    - Auth: ``Basic`` prefix (api_key already base64-encoded by caller).
    - Response: JSON ``{audioContent: <base64>}``.
    - Defaults: voiceId=``Alex``, modelId=``inworld-tts-1.5-mini``.
    """
    import base64

    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "text": input_text,
        "voiceId": voice or "Alex",
        "modelId": tts_model or "inworld-tts-1.5-mini",
        "audioConfig": {"audioEncoding": "MP3"},
    }
    resp = await client.post(base_url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"Inworld TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    data = resp.json()
    audio_b64 = data.get("audioContent")
    if not audio_b64:
        raise ValueError("Inworld TTS returned no audioContent")
    return base64.b64decode(audio_b64), "audio/mpeg"


async def tts_cartesia(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """Cartesia TTS — POST {base_url} body {model_id, transcript, voice, output_format}.

    - Auth: ``X-API-Key`` header (NOT Bearer).
    - Requires ``Cartesia-Version: 2024-06-10`` header.
    - Voice format: ``{mode: "id", id: <voiceId>}`` (only sent if voice given).
    - Response: binary MP3 (we request mp3 @ 128kbps / 44.1kHz).
    """
    if not tts_model:
        raise ValueError("Cartesia TTS requires a model (e.g. 'sonic-2')")

    headers = {
        "X-API-Key": api_key,
        "Cartesia-Version": "2024-06-10",
        "Content-Type": "application/json",
    }
    body: dict = {
        "model_id": tts_model,
        "transcript": input_text,
        "output_format": {
            "container": "mp3",
            "bit_rate": 128000,
            "sample_rate": 44100,
        },
    }
    if voice:
        body["voice"] = {"mode": "id", "id": voice}

    resp = await client.post(base_url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"Cartesia TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    audio = resp.content
    if not audio:
        raise ValueError("Cartesia TTS returned empty audio")
    content_type = resp.headers.get("content-type") or _format_to_mime("mp3")
    return audio, content_type


async def tts_playht(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    api_key: str,
    tts_model: str,
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """PlayHT TTS — POST {base_url} body {text, voice, voice_engine}.

    - ``api_key`` is ``"<userId>:<apiKey>"`` colon-joined. Split it.
    - Headers: ``X-USER-ID`` + ``Authorization: Bearer <key>`` + ``Accept: audio/mpeg``.
    - ``voice`` is typically an S3 manifest URL.
    - Response: streaming binary MP3.
    """
    user_id, _, key = (api_key or "").partition(":")
    if not user_id or not key:
        raise ValueError(
            "PlayHT TTS requires apiKey in 'userId:apiKey' format"
        )
    if not voice:
        raise ValueError("PlayHT TTS requires a voice (S3 manifest URL)")

    headers = {
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
        "X-USER-ID": user_id,
        "Authorization": f"Bearer {key}",
    }
    body = {
        "text": input_text,
        "voice": voice,
        "voice_engine": tts_model or "PlayDialog",
        "output_format": "mp3",
        "speed": 1,
    }
    resp = await client.post(base_url, json=body, headers=headers)
    if not resp.is_success:
        raise ValueError(
            f"PlayHT TTS failed: {resp.status_code} — {resp.text[:300]}"
        )
    audio = resp.content
    if not audio:
        raise ValueError("PlayHT TTS returned empty audio")
    return audio, "audio/mpeg"


async def tts_edge_tts(
    _client: httpx.AsyncClient,
    *,
    base_url: str = "",
    api_key: str = "",
    tts_model: str = "",
    voice: str,
    input_text: str,
    response_format: str = "mp3",
    **_kwargs,
) -> tuple[bytes, str]:
    """Microsoft Edge TTS — free, no API key required.

    Uses the edge-tts Python package which handles WebSocket communication
    with Microsoft's Bing speech synthesis service.

    Voice is the ShortName from the voice list (e.g. 'en-US-AriaNeural').
    ``tts_model`` is ignored; ``voice`` is required.
    ``api_key`` is ignored (no auth needed).
    """
    if not voice:
        raise ValueError("Edge TTS requires a voice (e.g. 'en-US-AriaNeural')")

    import edge_tts

    communicate = edge_tts.Communicate(input_text, voice)
    audio_chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    audio = b"".join(audio_chunks)
    if not audio:
        raise ValueError("Edge TTS returned empty audio")

    # edge-tts returns MP3 by default
    content_type = _format_to_mime(response_format) if response_format != "mp3" else "audio/mpeg"
    return audio, content_type


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch table — provider ID → adapter callable
# ─────────────────────────────────────────────────────────────────────────────

#: Type alias for adapter signature.
TTSAdapter = Callable[..., Awaitable[tuple[bytes, str]]]

TTS_ADAPTERS: dict[str, TTSAdapter] = {
    # Group A (Iterasi 1) — OpenAI-compatible + Hyperbolic
    "openai": tts_openai_compatible,
    "siliconflow": tts_openai_compatible,
    "hyperbolic": tts_hyperbolic,
    # Group B (Iterasi 2) — provider-specific
    "gemini": tts_gemini,
    "elevenlabs": tts_elevenlabs,
    "minimax": tts_minimax,
    "minimax-cn": tts_minimax,  # Same adapter, different base_url (set per-connection)
    "openrouter": tts_openrouter,
    # Group B-2 (Iterasi 3) — simple binary providers
    "deepgram": tts_deepgram,
    "nvidia": tts_nvidia,
    "huggingface": tts_huggingface,
    "inworld": tts_inworld,
    "cartesia": tts_cartesia,
    "playht": tts_playht,
    # Group C — free/local providers
    "edge-tts": tts_edge_tts,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _format_to_mime(fmt: str) -> str:
    """Map OpenAI response_format names to MIME types."""
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "pcm": "audio/L16",
    }.get(fmt, "audio/mpeg")

