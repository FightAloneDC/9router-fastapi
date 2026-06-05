"""Groq model fetching — uses shared helper."""

from app.providers.groq.config import GroqConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: GroqConfig = GroqConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Groq API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Groq."""
    return await fetch_models_header_auth(_config, api_key)
