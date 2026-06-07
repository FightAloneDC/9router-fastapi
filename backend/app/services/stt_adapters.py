"""
STT (Speech-to-Text) support for /v1/audio/transcriptions.

Provider-specific STT logic lives in ``backend/app/providers/<provider>/handler.py``
via ``execute_stt()`` method (PS pattern).

This file provides only the shared MIME helper used by the router.
"""
from __future__ import annotations

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
