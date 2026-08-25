"""Voyage AI model catalog.

Voyage does not publish a list-models API. Official docs
(https://docs.voyageai.com/docs/embeddings.md and siblings, retrieved
2026-08-25) only expose POST inference. Fetch returns the documented
catalog. Deprecated ids and Hugging Face-only `voyage-4-nano` are
omitted. Older models marked still accessible stay in the list.
"""

from app.providers.voyage_ai.config import VoyageAiConfig

_CONFIG = VoyageAiConfig()


def _model(model_id: str, kind: str) -> dict:
    return {"id": model_id, "name": model_id, "type": kind}


# Built from config.MODEL_TYPE_OVERRIDES so the catalog cannot
# drift from identity/types. Docs:
# https://docs.voyageai.com/docs/embeddings.md
# https://docs.voyageai.com/docs/contextualized-chunk-embeddings.md
# https://docs.voyageai.com/docs/multimodal-embeddings.md
# https://docs.voyageai.com/docs/reranker.md
HARDCODED_MODELS: list[dict] = [
    _model(model_id, kind)
    for model_id, kind in _CONFIG.MODEL_TYPE_OVERRIDES.items()
]


def parse_response(data: dict) -> list[dict]:
    """Voyage has no list-models response body."""
    del data
    return []


async def fetch_models(
    api_key: str,
    data: dict | None = None,
) -> list[dict]:
    """Return the documented catalog. Voyage has no list-models API."""
    del api_key, data
    return list(HARDCODED_MODELS)
