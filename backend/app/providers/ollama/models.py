"""Ollama Cloud model fetching — custom parse (models key)."""

from app.providers.ollama.config import OllamaConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: OllamaConfig = OllamaConfig()


def parse_ollama(data: dict) -> list[dict]:
    """Ollama returns {models: [...]}."""
    return data.get("models", [])


def parse_response(data: dict) -> list[dict]:
    return parse_ollama(data)


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Ollama Cloud."""
    return await fetch_models_header_auth(_config, api_key, parse_fn=parse_ollama)
