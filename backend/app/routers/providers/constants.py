"""Provider defaults, internal keys, and filter definitions."""

import re

from app.providers import get_all_model_type_overrides

# Fields stored in the data JSON blob that are NOT provider-specific config
# (they have dedicated output schema fields or are sensitive)
_DATA_INTERNAL_KEYS = {
    "apiKey", "accessToken", "refreshToken", "idToken",
    "models", "roundRobin", "baseUrl", "testStatus",
    "displayName", "globalPriority", "defaultModel",
    "lastError", "lastErrorAt", "errorCode",
    "anomaly", "anomalyReason", "anomalyAt",
    "anomalyRequestId",
    "expiresAt", "lastUsedAt", "consecutiveUseCount",
}

# Sensitive fields to strip from output
_SENSITIVE_KEYS = {"apiKey", "accessToken", "refreshToken", "idToken"}

# Filter definitions for suggested models
SUGGESTED_MODELS_FILTERS = {
    "openrouter-free": lambda models: sorted(
        [
            {"id": m.get("id"), "name": m.get("name"), "contextLength": m.get("context_length")}
            for m in models
            if m.get("pricing", {}).get("prompt") == "0"
            and m.get("pricing", {}).get("completion") == "0"
            and (m.get("context_length") or 0) >= 200000
        ],
        key=lambda x: -(x.get("contextLength") or 0),
    ),
    "opencode-free": lambda models: [
        {"id": m.get("id"), "name": m.get("id")}
        for m in models
        if m.get("id", "").endswith("-free")
           or m.get("id") == "big-pickle"
    ],
    "kilo-gateway": lambda models: [
        {"id": m.get("id"), "name": m.get("name") or m.get("id")}
        for m in models
        if m.get("id")
    ],
}

# ── Model Type System ──────────────────────────────────────────────────

# Lazy-loaded aggregated overrides from all providers
_MODEL_TYPE_OVERRIDES_CACHE: dict[str, str] | None = None


def _get_model_type_overrides() -> dict[str, str]:
    """Get aggregated MODEL_TYPE_OVERRIDES from all providers (cached)."""
    global _MODEL_TYPE_OVERRIDES_CACHE
    if _MODEL_TYPE_OVERRIDES_CACHE is None:
        _MODEL_TYPE_OVERRIDES_CACHE = get_all_model_type_overrides()
    return _MODEL_TYPE_OVERRIDES_CACHE


def infer_model_type(model_id: str) -> str:
    """Infer model type from model ID using regex heuristics."""
    mid = model_id.lower()

    # Check overrides first
    overrides = _get_model_type_overrides()
    if model_id in overrides:
        return overrides[model_id]

    # Rerank models (must precede embedding — e.g. gte-rerank-v2 contains "gte-")
    if re.search(r"rerank", mid):
        return "rerank"

    # Embedding models
    if re.search(r"embed|e5-|bge-|gte-|nomic|cohere-embed|voyage-", mid):
        return "embedding"

    # TTS models
    if re.search(r"tts|speech|audio|voice", mid):
        return "tts"

    # STT models
    if re.search(r"whisper|transcri|stt|asr", mid):
        return "stt"

    # Image models
    if re.search(r"image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion|midjourney", mid):
        return "image"

    # Default: LLM
    return "llm"


def normalize_models_list(models) -> list:
    """Normalize models list to always include type field (backward compat).

    Handles both old string format and new object format.
    """
    if not models:
        return []
    result = []
    for m in models:
        if isinstance(m, str):
            result.append({"id": m, "type": infer_model_type(m)})
        elif isinstance(m, dict):
            if "type" not in m:
                m["type"] = infer_model_type(m.get("id", ""))
            result.append(m)
    return result
