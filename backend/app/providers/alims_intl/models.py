"""Alibaba Studio model catalog.

Live ``GET {BASE_URL}/models`` covers chat / embed / image / TTS / STT.
Text Rerank ids are not listed there — merge documented rows from
``config.MODEL_TYPE_OVERRIDES`` so media kind ``rerank`` appears after
Fetch Models.
"""

from __future__ import annotations

from app.providers.alims_intl.config import AlimsIntlConfig
from app.providers.model_helpers import fetch_models_header_auth
from app.routers.providers.constants import infer_model_type

_CONFIG = AlimsIntlConfig()


def _catalog_row(model_id: str, kind: str | None = None) -> dict:
    mid = (model_id or "").strip()
    return {
        "id": mid,
        "name": mid,
        "type": kind or infer_model_type(mid),
    }


def parse_response(data: dict) -> list[dict]:
    """Normalize OpenAI-style ``{data: [...]}`` with typed rows."""
    rows: list[dict] = []
    for item in data.get("data") or []:
        if isinstance(item, str):
            mid = item.strip()
            if mid:
                rows.append(_catalog_row(mid))
            continue
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or "").strip()
        if not mid:
            continue
        override = _CONFIG.MODEL_TYPE_OVERRIDES.get(mid)
        kind = item.get("type") or override
        rows.append(_catalog_row(mid, kind if isinstance(kind, str) else None))
    return rows


def merge_docs_catalog(live: list[dict]) -> list[dict]:
    """Append docs-only ids (e.g. rerank) missing from live /models."""
    seen: set[str] = set()
    out: list[dict] = []
    for item in live:
        mid = str(item.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(item)
    for mid, kind in _CONFIG.MODEL_TYPE_OVERRIDES.items():
        if mid in seen:
            continue
        seen.add(mid)
        out.append(_catalog_row(mid, kind))
    return out


async def fetch_models(
    api_key: str,
    data: dict | None = None,
) -> list[dict]:
    """Live compatible-mode catalog plus docs-only rerank rows."""
    cfg = _CONFIG
    if isinstance(data, dict) and data.get("baseUrl"):
        cfg = AlimsIntlConfig(
            BASE_URL=str(data["baseUrl"]).rstrip("/"),
        )
    live = await fetch_models_header_auth(
        cfg,
        api_key,
        parse_fn=parse_response,
    )
    return merge_docs_catalog(live)
