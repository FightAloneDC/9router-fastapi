"""Gemini model fetching — query-param auth (?key=), custom parse."""

from app.providers.gemini.config import GeminiConfig
from app.providers.model_helpers import fetch_models_query_auth

_config: GeminiConfig = GeminiConfig()


def parse_gemini(data: dict) -> list[dict]:
    """Gemini returns {models: [{name: 'models/xxx', ...}]}."""
    models: list[dict] = data.get("models", [])
    for m in models:
        if "id" not in m and m.get("name"):
            m["id"] = m.get("name")
    return models


def parse_response(data: dict) -> list[dict]:
    return parse_gemini(data)


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Gemini."""
    return await fetch_models_query_auth(_config, api_key, parse_fn=parse_gemini)
