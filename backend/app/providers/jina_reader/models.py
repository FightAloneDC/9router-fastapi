"""Jina Reader model fetching — uses shared helper."""

from app.providers.jina_reader.config import JinaReaderConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: JinaReaderConfig = JinaReaderConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Jina Reader API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Jina Reader."""
    return await fetch_models_header_auth(_config, api_key)
