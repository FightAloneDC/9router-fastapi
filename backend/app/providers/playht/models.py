"""PlayHT model fetching.

PlayHT does not expose a standard model listing endpoint.
API key is in "userId:apiKey" format — used only for TTS requests.
"""

from app.providers.playht.config import PlayhtConfig

_config = PlayhtConfig()

TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """No model listing available for PlayHT."""
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """PlayHT does not expose a model listing endpoint.

    Args:
        api_key: PlayHT API key (unused — no model listing).

    Returns:
        Empty list.
    """
    return []
