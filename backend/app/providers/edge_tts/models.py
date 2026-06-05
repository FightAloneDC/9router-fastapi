"""Edge TTS model fetching — no auth, uses espeak/edge-tts."""

from app.providers.edge_tts.config import EdgeTtsConfig

_config: EdgeTtsConfig = EdgeTtsConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Edge TTS voices are fetched via voice_fetchers, not model listing."""
    return []
