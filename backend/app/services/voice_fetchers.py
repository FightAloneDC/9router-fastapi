"""Voice fetcher adapters for GET /v1/audio/voices.

Dispatches to provider handlers (PS pattern) for voice listing.
Only local-device (OS-level, not a provider) uses a fallback function here.

Plan: docs/plans/v1-audio-voices.md (Phase 1 + 2).
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import time
from typing import Any

import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Local device (not a provider — OS-level)
# ─────────────────────────────────────────────────────────────────────────────


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
    """Dispatch to the correct voice fetcher and optionally filter by lang.

    Tries provider handler first (PS pattern), falls back to legacy per-provider
    functions for local-device (not a real provider).
    """
    # Try handler dispatch (PS pattern)
    try:
        from app.providers.provider import Provider
        p = Provider(provider)
        handler = p.handler()
        if hasattr(handler, "fetch_voices"):
            voices = await handler.fetch_voices(client, api_key)
            if lang:
                voices = [v for v in voices if v.get("lang") == lang]
            return voices
    except (ValueError, ModuleNotFoundError):
        pass

    # Fallback: local-device (not a provider, OS-level)
    if provider == "local-device":
        voices = await fetch_local_device_voices()
        if lang:
            voices = [v for v in voices if v.get("lang") == lang]
        return voices

    raise ValueError(f"Provider '{provider}' does not support voice listing")


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
