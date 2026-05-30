"""Voice fetcher adapters for GET /v1/audio/voices.

Each adapter returns a list of voice dicts with at minimum:
    {id, name, lang, gender}

The route handler normalizes these into OpenAI-compatible voice list format
with a ``model`` field pre-formatted as ``{alias}/{voice_id}``.

Plan: docs/plans/v1-audio-voices.md (Phase 1 + 2).
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import time
from typing import Any

import httpx


# Providers that expose TTS voices via this aggregator.
VOICE_FETCHER_PROVIDERS: set[str] = {
    "elevenlabs",
    "deepgram",
    "inworld",
    "edge-tts",
    "local-device",
    "minimax",
    "minimax-cn",
    "gemini",
}

# Providers whose adapter does NOT need an API key.
_NO_KEY_PROVIDERS: set[str] = {"edge-tts", "local-device", "gemini"}


# ─────────────────────────────────────────────────────────────────────────────
# Individual voice fetchers
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_elevenlabs_voices(
    client: httpx.AsyncClient, api_key: str
) -> list[dict[str, Any]]:
    """Fetch ElevenLabs voices via GET /v1/voices."""
    if not api_key:
        raise ValueError("ElevenLabs requires an API key")
    resp = await client.get(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key},
    )
    resp.raise_for_status()

    voices: list[dict[str, Any]] = []
    for v in resp.json().get("voices", []) or []:
        voices.append(
            {
                "id": v.get("voice_id", ""),
                "name": v.get("name", ""),
                "lang": v.get("labels", {}).get("language", "en"),
                "gender": v.get("labels", {}).get("gender", ""),
            }
        )
    return voices


async def fetch_deepgram_voices(
    client: httpx.AsyncClient, api_key: str
) -> list[dict[str, Any]]:
    """Fetch Deepgram TTS models (each model = one voice).

    Endpoint: GET https://api.deepgram.com/v1/models  (auth: Token header)
    Response has ``tts`` array.
    """
    if not api_key:
        raise ValueError("Deepgram requires an API key")
    resp = await client.get(
        "https://api.deepgram.com/v1/models",
        headers={"Authorization": f"Token {api_key}"},
    )
    resp.raise_for_status()
    data = resp.json()

    voices: list[dict[str, Any]] = []
    for m in data.get("tts", []) or []:
        langs = m.get("languages", ["en"]) or ["en"]
        voice_id = m.get("canonical_name") or m.get("name", "")
        gender = ""
        for tag in (m.get("metadata") or {}).get("tags", []) or []:
            if tag in ("masculine", "feminine"):
                gender = tag
                break
        for lang in langs:
            voices.append(
                {
                    "id": voice_id,
                    "name": m.get("name", voice_id),
                    "lang": lang,
                    "gender": gender,
                }
            )
    return voices


async def fetch_inworld_voices(
    client: httpx.AsyncClient, api_key: str
) -> list[dict[str, Any]]:
    """Fetch Inworld TTS voices via GET /tts/v1/voices.

    Auth: Basic base64(api_key).
    """
    if not api_key:
        raise ValueError("Inworld requires an API key")
    resp = await client.get(
        "https://api.inworld.ai/tts/v1/voices",
        headers={"Authorization": f"Basic {api_key}"},
    )
    resp.raise_for_status()

    voices: list[dict[str, Any]] = []
    for v in resp.json().get("voices", []) or []:
        langs = v.get("languages", ["en"]) or ["en"]
        voice_id = v.get("voiceId", "")
        for lang in langs:
            voices.append(
                {
                    "id": voice_id,
                    "name": v.get("displayName", voice_id),
                    "lang": lang,
                    "gender": v.get("gender", ""),
                }
            )
    return voices


async def fetch_edge_tts_voices(
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Fetch Microsoft Edge TTS voices (no auth required)."""
    resp = await client.get(
        "https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/"
        "voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4",
    )
    resp.raise_for_status()
    payload = resp.json()

    voices: list[dict[str, Any]] = []
    items = payload if isinstance(payload, list) else payload.get("voices", [])
    for v in items:
        locale = v.get("Locale", "")
        lang = locale.split("-")[0] if locale else "en"
        friendly = v.get("FriendlyName", v.get("ShortName", ""))
        name = friendly.replace("Microsoft ", "").replace(
            " Online (Natural) - ", " ("
        )
        voices.append(
            {
                "id": v.get("ShortName", ""),
                "name": name,
                "lang": lang,
                "gender": (v.get("Gender", "") or "").lower(),
            }
        )
    return voices


async def fetch_minimax_voices(
    client: httpx.AsyncClient,
    api_key: str,
    provider: str = "minimax",
) -> list[dict[str, Any]]:
    """Fetch MiniMax voices via POST /v1/get_voice."""
    if not api_key:
        raise ValueError("MiniMax requires an API key")
    endpoints = {
        "minimax": "https://api.minimax.io/v1/get_voice",
        "minimax-cn": "https://api.minimaxi.com/v1/get_voice",
    }
    url = endpoints.get(provider)
    if not url:
        raise ValueError(f"Unknown minimax provider: {provider}")

    resp = await client.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"voice_type": "all"},
    )
    resp.raise_for_status()
    data = resp.json()

    # MiniMax error envelope
    base_resp = data.get("base_resp") or data.get("baseResp") or {}
    status_code = (
        base_resp.get("status_code")
        if base_resp.get("status_code") is not None
        else base_resp.get("statusCode", 0)
    )
    if status_code != 0:
        raise Exception(
            base_resp.get("status_msg")
            or base_resp.get("statusMsg")
            or "MiniMax error"
        )

    voices: list[dict[str, Any]] = []
    for group_key, group_label in [
        ("system_voice", "System"),
        ("voice_cloning", "Cloned"),
        ("voice_generation", "Generated"),
    ]:
        for item in data.get(group_key, []) or []:
            voice_id = item.get("voice_id") or item.get("voiceId", "")
            voice_name = (
                item.get("voice_name")
                or item.get("voiceName")
                or voice_id
            )
            lang = "Custom"
            if group_key == "system_voice" and "_" in voice_id:
                lang = voice_id.split("_")[0]
            voices.append(
                {
                    "id": voice_id,
                    "name": (
                        f"{voice_name} · {group_label}"
                        if group_key != "system_voice"
                        else voice_name
                    ),
                    "lang": lang,
                    "gender": "",
                }
            )
    return voices


# Gemini has no voice list API — 30 prebuilt voices documented by Google.
GEMINI_VOICES: list[dict[str, str]] = [
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


async def fetch_gemini_voices() -> list[dict[str, Any]]:
    """Return hardcoded Gemini TTS voices (no list API available)."""
    return [dict(v) for v in GEMINI_VOICES]


async def fetch_local_device_voices() -> list[dict[str, Any]]:
    """Fetch local OS TTS voices (Linux espeak / macOS say).

    Dockerized Linux backend -> espeak. Returns [] if espeak missing.
    Runs subprocess in thread pool to stay non-blocking.
    """
    system = platform.system()
    voices: list[dict[str, Any]] = []

    async def _run_espeak() -> None:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["espeak", "--voices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 4:
                voices.append(
                    {
                        "id": parts[3],
                        "name": parts[3],
                        "lang": parts[1].split("-")[0] if len(parts) > 1 else "en",
                        "gender": "male" if "M" in parts[0] else "female",
                    }
                )

    async def _run_say() -> None:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return
        for line in result.stdout.strip().split("\n"):
            parts = line.split()
            if parts:
                voices.append(
                    {
                        "id": parts[0],
                        "name": parts[0],
                        "lang": parts[1].split("_")[0] if len(parts) > 1 else "en",
                        "gender": "",
                    }
                )

    if system == "Linux":
        await _run_espeak()
    elif system == "Darwin":
        await _run_say()
    return voices


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch + cache
# ─────────────────────────────────────────────────────────────────────────────


async def fetch_voices_for_provider(
    client: httpx.AsyncClient,
    provider: str,
    api_key: str = "",
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the correct voice fetcher and optionally filter by lang."""
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

    if lang:
        voices = [v for v in voices if v.get("lang") == lang]
    return voices


# In-memory cache: ``{cache_key: (timestamp, voices)}``
_voice_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
VOICE_CACHE_TTL = 3600  # 1 hour


async def fetch_voices_cached(
    client: httpx.AsyncClient,
    provider: str,
    api_key: str = "",
    lang: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch voices with in-memory 1h TTL cache."""
    cache_key = f"{provider}:{lang or 'all'}"
    now = time.time()
    if cache_key in _voice_cache:
        cached_time, cached_voices = _voice_cache[cache_key]
        if now - cached_time < VOICE_CACHE_TTL:
            return cached_voices
    voices = await fetch_voices_for_provider(client, provider, api_key, lang)
    _voice_cache[cache_key] = (now, voices)
    return voices


def is_no_key_provider(provider: str) -> bool:
    """Return True if provider doesn't need an API key."""
    return provider in _NO_KEY_PROVIDERS
