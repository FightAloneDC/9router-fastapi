"""AskCodi model fetching — uses shared helper."""

from app.providers.askcodi.config import AskcodiConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: AskcodiConfig = AskcodiConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from AskCodi API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from AskCodi."""
    return await fetch_models_header_auth(_config, api_key)
