"""Ollama Local model fetching — no auth, custom parse (models key)."""

from app.providers.ollama_local.config import OllamaLocalConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: OllamaLocalConfig = OllamaLocalConfig()


def parse_ollama_local(data: dict) -> list[dict]:
    """Ollama returns {models: [...]}."""
    return data.get("models", [])


def parse_response(data: dict) -> list[dict]:
    return parse_ollama_local(data)


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Ollama Local."""
    return await fetch_models_header_auth(_config, api_key, parse_fn=parse_ollama_local)
