"""BytePlus ModelArk model fetching — uses shared helper."""

from app.providers.byteplus.config import ByteplusConfig
from app.providers.model_helpers import fetch_models_header_auth

_config: ByteplusConfig = ByteplusConfig()


def parse_response(data: dict) -> list[dict]:
    """Extract models list from BytePlus ModelArk API response."""
    return data.get("data", [])


async def fetch_models(api_key: str) -> list[dict]:
    """Fetch available models from BytePlus ModelArk."""
    return await fetch_models_header_auth(_config, api_key)
