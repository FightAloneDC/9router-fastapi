"""Google PSE model fetching — uses shared helper."""

from app.providers.google_pse.config import GooglePseConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: GooglePseConfig = GooglePseConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from Google PSE API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from Google PSE."""
    return await fetch_models_header_auth(_config, api_key)
