"""
TTS (Text-to-Speech) support for /v1/audio/speech.

Provider-specific TTS logic lives in ``backend/app/providers/<provider>/handler.py``
via ``execute_tts()`` method (PS pattern).

This file is intentionally empty — all TTS logic has been moved to provider handlers.
"""
