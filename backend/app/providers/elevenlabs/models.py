"""ElevenLabs model fetching — custom parse (plain list, model_id)."""

from app.providers.elevenlabs.config import ElevenlabsConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: ElevenlabsConfig = ElevenlabsConfig()


def parse_elevenlabs(data: list | dict) -> list[dict]:
    """ElevenLabs returns plain list, not {data: [...]}."""
    models: list = data if isinstance(data, list) else data.get("data", [])
    for m in models:
        if isinstance(m, dict) and "id" not in m and m.get("model_id"):
            m["id"] = m.get("model_id")
    return models


def parse_response(data: dict) -> list[dict]:
    return parse_elevenlabs(data)


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from ElevenLabs."""
    return await fetch_models_header_auth(_config, api_key, parse_fn=parse_elevenlabs)
