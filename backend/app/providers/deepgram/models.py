"""Deepgram model fetching — custom parse (stt/tts sections, Token auth)."""

from app.providers.deepgram.config import DeepgramConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: DeepgramConfig = DeepgramConfig()


def parse_deepgram(data: dict) -> list[dict]:
    """Deepgram returns {stt: [...], tts: [...]}."""
    models: list[dict] = []
    for m in data.get("stt", []):
        if isinstance(m, dict):
            if "id" not in m:
                m["id"] = m.get("canonical_name") or m.get("name", "")
            models.append(m)
    for m in data.get("tts", []):
        if isinstance(m, dict):
            if "id" not in m:
                m["id"] = m.get("canonical_name") or m.get("name", "")
            models.append(m)
    return models


def parse_response(data: dict) -> list[dict]:
    return parse_deepgram(data)


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Deepgram."""
    return await fetch_models_header_auth(_config, api_key, parse_fn=parse_deepgram)
