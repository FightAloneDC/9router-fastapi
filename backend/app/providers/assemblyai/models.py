"""AssemblyAI model fetching — no API listing, hardcoded models."""

from app.providers.assemblyai.config import AssemblyaiConfig

_config: AssemblyaiConfig = AssemblyaiConfig()

HARDCODED_MODELS: list[dict] = [
    {"id": "universal-3-pro", "name": "universal-3-pro", "type": "stt"},
    {"id": "universal-2", "name": "universal-2", "type": "stt"},
    {"id": "nano", "name": "nano", "type": "stt"},
    {"id": "best", "name": "best", "type": "stt"},
    {"id": "slam-1", "name": "slam-1", "type": "stt"},
]


def parse_response(data: dict) -> list[dict]:
    """No model listing available for AssemblyAI."""
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """AssemblyAI does not expose a standard model listing endpoint."""
    return HARDCODED_MODELS
