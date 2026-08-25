"""Jina AI model catalog — live GET /v1/models + web rows.

Live list uses ``config.BASE_URL`` (+ connection ``baseUrl``).
Strip ``{PROVIDER_ID}/`` prefix for proxy ids.

Search (``SEARCH_BASE_URL``) and Reader (``READER_BASE_URL``) have
no list-models API — append synthetic ``search`` / ``reader`` rows
so media kinds webSearch / webFetch appear under the same
provider (one API key).
"""

from __future__ import annotations

from typing import Any

from app.providers.jina_ai.config import JinaAiConfig
from app.providers.model_helpers import fetch_models_header_auth

_CONFIG = JinaAiConfig()


def _list_prefix() -> str:
    return f"{_CONFIG.PROVIDER_ID}/"


def _bare_id(raw: str) -> str:
    mid = (raw or "").strip()
    prefix = _list_prefix()
    if mid.startswith(prefix):
        return mid[len(prefix) :]
    return mid


def _infer_kind(model_id: str, item: dict[str, Any]) -> str:
    mid = model_id.lower()
    if "rerank" in mid or "colbert" in mid:
        return "rerank"
    outs = item.get("output_modalities") or []
    if isinstance(outs, list) and "embeddings" in outs:
        return "embedding"
    if any(tok in mid for tok in ("embed", "clip")):
        return "embedding"
    return "llm"


def parse_response(data: dict) -> list[dict]:
    """Normalize live /models payload to {id, name, type}."""
    rows: list[dict] = []
    for item in data.get("data") or []:
        if not isinstance(item, dict):
            continue
        model_id = _bare_id(str(item.get("id") or ""))
        if not model_id:
            continue
        name = str(item.get("name") or model_id)
        rows.append(
            {
                "id": model_id,
                "name": name,
                "type": _infer_kind(model_id, item),
            }
        )
    return rows


async def fetch_models(
    api_key: str,
    data: dict | None = None,
) -> list[dict]:
    """Live BASE_URL catalog plus synthetic search/reader."""
    cfg = _CONFIG
    if isinstance(data, dict) and data.get("baseUrl"):
        cfg = JinaAiConfig(
            BASE_URL=str(data["baseUrl"]).rstrip("/"),
        )
    live = await fetch_models_header_auth(
        cfg,
        api_key,
        parse_fn=parse_response,
    )
    return list(live) + list(_CONFIG.WEB_CATALOG)
