"""Google TTS model fetching — no standard listing."""

from app.providers.google_tts.config import GoogleTtsConfig

_config: GoogleTtsConfig = GoogleTtsConfig()


def parse_response(data: dict) -> list[dict]:
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """Google TTS does not expose a standard model listing endpoint."""
    return []
