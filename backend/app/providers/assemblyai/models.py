"""AssemblyAI model fetching.

AssemblyAI does not expose a standard /v1/models endpoint.
"""

from app.providers.assemblyai.config import AssemblyAIConfig

_config = AssemblyAIConfig()

TIMEOUT = 15.0


def parse_response(data: dict) -> list:
    """No model listing available for AssemblyAI."""
    return []


async def fetch_models(api_key: str) -> list[dict]:
    """AssemblyAI does not expose a standard model listing endpoint.

    Args:
        api_key: AssemblyAI API key (unused — no model listing).

    Returns:
        Empty list.
    """
    return []
