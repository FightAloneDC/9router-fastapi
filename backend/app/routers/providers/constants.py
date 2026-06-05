"""Provider defaults, internal keys, and filter definitions."""

import re


# Fields stored in the data JSON blob that are NOT provider-specific config
# (they have dedicated output schema fields or are sensitive)
_DATA_INTERNAL_KEYS = {
    "apiKey", "accessToken", "refreshToken", "idToken",
    "models", "roundRobin", "baseUrl", "testStatus",
    "displayName", "globalPriority", "defaultModel",
    "lastError", "lastErrorAt", "errorCode",
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
    ],
    "kilo-gateway": lambda models: [
        {"id": m.get("id"), "name": m.get("name") or m.get("id")}
        for m in models
        if m.get("id")
    ],
}

# ── Model Type System ──────────────────────────────────────────────────

MODEL_TYPE_OVERRIDES = {
    "text-embedding-3-small": "embedding",
    "text-embedding-3-large": "embedding",
    "text-embedding-ada-002": "embedding",
    "mistral-embed": "embedding",
    "nomic-ai/nomic-embed-text-v1.5": "embedding",
    "voyage-3-large": "embedding",
    "voyage-3.5": "embedding",
    "voyage-3.5-lite": "embedding",
    "voyage-code-3": "embedding",
    "voyage-finance-2": "embedding",
    "voyage-law-2": "embedding",
    "voyage-multilingual-2": "embedding",
    "jina-embeddings-v3": "embedding",
    "jina-embeddings-v2-base-en": "embedding",
    "jina-embeddings-v2-base-code": "embedding",
    "BAAI/bge-large-en-v1.5": "embedding",
    "togethercomputer/m2-bert-80M-8k-retrieval": "embedding",
    "Qwen/Qwen3-Embedding-8B": "embedding",
    "nvidia/nv-embedqa-e5-v5": "embedding",
    "whisper-1": "stt",
    "whisper-large-v3": "stt",
    "whisper-large-v3-turbo": "stt",
    "distil-whisper-large-v3-en": "stt",
    "whisper-large": "stt",
    "nova-3": "stt",
    "nova-2": "stt",
    "universal-3-pro": "stt",
    "universal-2": "stt",
    "gpt-4o-transcribe": "stt",
    "gpt-4o-mini-transcribe": "stt",
    "tts-1": "tts",
    "tts-1-hd": "tts",
    "gpt-4o-mini-tts": "tts",
    "fastpitch": "tts",
    "tacotron2": "tts",
    "eleven_multilingual_v2": "tts",
    "eleven_turbo_v2_5": "tts",
    "sonic-2": "tts",
    "sonic-3": "tts",
    "PlayDialog": "tts",
    "Play3.0-mini": "tts",
    "speech-2.8-hd": "tts",
    "speech-2.8-turbo": "tts",
    "speech-2.6-hd": "tts",
    "speech-2.6-turbo": "tts",
    "speech-02-hd": "tts",
    "speech-02-turbo": "tts",
    "speech-01-hd": "tts",
    "speech-01-turbo": "tts",
    "dall-e-3": "image",
    "dall-e-2": "image",
    "gemini-2.5-flash-preview-tts": "tts",
    "gemini-2.5-pro-preview-tts": "tts",
    "text-embedding-004": "embedding",
    "embedding-001": "embedding",
    "melo-tts": "tts",
    "inworld-tts-1.5-mini": "tts",
    "inworld-tts-1.5-max": "tts",
    "tts_models/en/ljspeech/tacotron2-DDC": "tts",
    "tortoise-v2": "tts",
    "facebook/mms-tts-eng": "tts",
    "microsoft/speecht5_tts": "tts",
    "openai/whisper-large-v3": "stt",
    "openai/whisper-small": "stt",
}


def infer_model_type(model_id: str) -> str:
    """Infer model type from model ID using regex heuristics."""
    mid = model_id.lower()

    # Check overrides first
    if model_id in MODEL_TYPE_OVERRIDES:
        return MODEL_TYPE_OVERRIDES[model_id]

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
