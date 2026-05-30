"""Provider defaults, internal keys, and filter definitions."""

import re

# Default base URLs per provider
# Validation types: "openai" (GET /models with Bearer), "anthropic" (GET /models with x-api-key),
# "google" (GET /models?key=), "azure" (custom), "vertex" (custom), "cookie" (custom)
PROVIDER_DEFAULTS = {
    # ── Standard API Key providers ──────────────────────────────────────
    "openai": {"baseUrl": "https://api.openai.com/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"]},
    "opencode-go": {"baseUrl": "https://opencode.ai/zen/go/v1", "validationType": "openai"},
    "anthropic": {"baseUrl": "https://api.anthropic.com/v1", "validationType": "anthropic", "serviceKinds": ["llm", "imageToText"]},
    "askcodi": {"baseUrl": "https://api.askcodi.com/v1", "validationType": "openai"},
    "google": {"baseUrl": "https://generativelanguage.googleapis.com/v1beta", "validationType": "google"},
    "gemini": {"baseUrl": "https://generativelanguage.googleapis.com/v1beta", "validationType": "google", "serviceKinds": ["llm", "embedding", "image", "imageToText", "webSearch", "tts", "stt"]},
    "openrouter": {"baseUrl": "https://openrouter.ai/api/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding", "tts", "imageToText"]},
    "deepseek": {"baseUrl": "https://api.deepseek.com", "validationType": "openai"},
    "groq": {"baseUrl": "https://api.groq.com/openai/v1", "validationType": "openai", "serviceKinds": ["llm", "imageToText", "stt"]},
    "mistral": {"baseUrl": "https://api.mistral.ai/v1", "validationType": "openai", "serviceKinds": ["llm", "imageToText", "embedding"]},
    "cohere": {"baseUrl": "https://api.cohere.com/compatibility/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding"]},
    "fireworks": {"baseUrl": "https://api.fireworks.ai/inference/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding"]},
    "together": {"baseUrl": "https://api.together.xyz/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding"]},
    "xai": {"baseUrl": "https://api.x.ai/v1", "validationType": "openai", "serviceKinds": ["llm", "imageToText", "webSearch"]},
    "cerebras": {"baseUrl": "https://api.cerebras.ai/v1", "validationType": "openai"},
    "nebius": {"baseUrl": "https://api.studio.nebius.ai/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding"]},
    "hyperbolic": {"baseUrl": "https://api.hyperbolic.xyz/v1", "validationType": "openai", "serviceKinds": ["llm", "tts"]},
    "perplexity": {"baseUrl": "https://api.perplexity.ai", "validationType": "openai", "serviceKinds": ["llm", "webSearch"]},
    "nvidia": {"baseUrl": "https://integrate.api.nvidia.com/v1", "validationType": "openai", "serviceKinds": ["llm", "tts", "embedding"]},
    "siliconflow": {"baseUrl": "https://api.siliconflow.com/v1", "validationType": "openai", "serviceKinds": ["llm", "embedding", "image", "tts"]},
    "volcengine-ark": {"baseUrl": "https://ark.cn-beijing.volces.com/api/coding/v3", "validationType": "openai"},
    "volcengine": {"baseUrl": "https://ark.cn-beijing.volces.com/api/v3", "validationType": "openai"},
    "byteplus": {"baseUrl": "https://ark.ap-southeast.bytepluses.com/api/coding/v3", "validationType": "openai", "serviceKinds": ["llm"]},
    "alicode": {"baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "validationType": "openai"},
    "alicode-intl": {"baseUrl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "validationType": "openai"},
    "nanobanana": {"baseUrl": "https://api.nanobananaapi.ai/v1", "validationType": "openai", "serviceKinds": ["image"]},
    "chutes": {"baseUrl": "https://llm.chutes.ai/v1", "validationType": "openai"},
    "assemblyai": {"baseUrl": "https://api.assemblyai.com/v1", "validationType": "assemblyai", "serviceKinds": ["stt"]},
    "vercel-ai-gateway": {"baseUrl": "https://ai-gateway.vercel.sh/v1", "validationType": "openai", "serviceKinds": ["llm"]},
    # ── Claude-format providers (use Anthropic-compatible API) ──────────
    "glm": {"baseUrl": "https://api.z.ai/api/anthropic/v1", "validationType": "anthropic"},
    "kimi": {"baseUrl": "https://api.kimi.com/coding/v1", "validationType": "anthropic", "serviceKinds": ["llm", "webSearch"]},
    "minimax": {"baseUrl": "https://api.minimax.io/anthropic/v1", "validationType": "anthropic", "serviceKinds": ["llm", "image", "imageToText", "webSearch", "tts"]},
    "minimax-cn": {"baseUrl": "https://api.minimaxi.com/anthropic/v1", "validationType": "anthropic", "serviceKinds": ["llm", "tts"]},
    # ── OpenAI-format Chinese providers ─────────────────────────────────
    "glm-cn": {"baseUrl": "https://open.bigmodel.cn/api/coding/paas/v4", "validationType": "openai"},
    "xiaomi-mimo": {"baseUrl": "https://api.xiaomimimo.com/v1", "validationType": "openai"},
    "xiaomi-tokenplan": {"baseUrl": "https://token-plan-sgp.xiaomimimo.com/v1", "validationType": "openai"},
    # ── Cloud/infrastructure providers ──────────────────────────────────
    "huggingface": {"baseUrl": "https://api-inference.huggingface.co/v1", "validationType": "openai", "serviceKinds": ["image", "imageToText", "tts", "stt"]},
    "azure": {"validationType": "azure", "serviceKinds": ["llm", "embedding", "tts", "stt", "image"]},
    "vertex": {"validationType": "vertex"},
    "vertex-partner": {"validationType": "vertex"},
    "amazon-bedrock": {"validationType": "openai"},  # needs providerSpecificData
    "cloudflare-ai": {"baseUrl": "https://api.cloudflare.com/client/v4", "validationType": "cloudflare", "serviceKinds": ["llm", "image"]},
    # ── Ollama ──────────────────────────────────────────────────────────
    "ollama": {"baseUrl": "http://localhost:11434", "validationType": "openai"},
    "ollama-local": {"baseUrl": "http://localhost:11434", "validationType": "openai"},
    # ── Web search providers ────────────────────────────────────────────
    "tavily": {"baseUrl": "https://api.tavily.com", "validationType": "openai", "serviceKinds": ["webSearch", "webFetch"]},
    "brave-search": {"baseUrl": "https://api.search.brave.com/res/v1", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "serper": {"baseUrl": "https://google.serper.dev", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "exa": {"baseUrl": "https://api.exa.ai", "validationType": "openai", "serviceKinds": ["webSearch", "webFetch"]},
    # ── Media providers ─────────────────────────────────────────────────
    "fal-ai": {"baseUrl": "https://fal.run", "validationType": "openai", "serviceKinds": ["image"]},
    "stability-ai": {"baseUrl": "https://api.stability.ai/v2beta", "validationType": "openai", "serviceKinds": ["image"]},
    "jina-ai": {"baseUrl": "https://api.jina.ai/v1", "validationType": "openai", "serviceKinds": ["embedding"]},
    # ── Web cookie providers ────────────────────────────────────────────
    "grok-web": {"validationType": "cookie", "serviceKinds": ["llm"]},
    "perplexity-web": {"validationType": "cookie", "serviceKinds": ["llm"]},
    # ── OAuth/free providers (validation not applicable) ────────────────
    "kiro": {"validationType": "openai"},
    "qwen": {"baseUrl": "https://portal.qwen.ai/v1", "validationType": "openai"},
    "gemini-cli": {"validationType": "google"},
    "iflow": {"baseUrl": "https://apis.iflow.cn/v1", "validationType": "openai"},
    "opencode": {"baseUrl": "https://opencode.ai", "validationType": "openai"},
    "claude": {"baseUrl": "https://api.anthropic.com/v1", "validationType": "anthropic"},
    "antigravity": {"validationType": "google"},
    "codex": {"baseUrl": "https://chatgpt.com/backend-api", "validationType": "openai", "serviceKinds": ["llm", "image"]},
    "github": {"baseUrl": "https://api.githubcopilot.com", "validationType": "openai", "serviceKinds": ["llm", "embedding"]},
    "cursor": {"baseUrl": "https://api2.cursor.sh", "validationType": "openai"},
    "kilocode": {"baseUrl": "https://api.kilo.ai/api/openrouter", "validationType": "openai"},
    "kilo-gateway": {"baseUrl": "https://api.kilo.ai/api/gateway", "validationType": "openai-chat"},
    "cline": {"baseUrl": "https://api.cline.bot/api/v1", "validationType": "openai"},
    "qoder": {"validationType": "openai", "serviceKinds": ["llm"]},
    # ── Additional media-only providers ─────────────────────────────────
    "elevenlabs": {"baseUrl": "https://api.elevenlabs.io", "validationType": "elevenlabs", "serviceKinds": ["tts"]},
    "cartesia": {"baseUrl": "https://api.cartesia.ai", "validationType": "openai", "serviceKinds": ["tts"]},
    "playht": {"baseUrl": "https://api.play.ht", "validationType": "openai", "serviceKinds": ["tts"]},
    "local-device": {"validationType": "noauth", "serviceKinds": ["tts"]},
    "google-tts": {"validationType": "noauth", "serviceKinds": ["tts"]},
    "edge-tts": {"baseUrl": "https://speech.platform.bing.com", "validationType": "noauth", "serviceKinds": ["tts"]},
    "coqui": {"validationType": "noauth", "serviceKinds": ["tts"]},
    "tortoise": {"validationType": "noauth", "serviceKinds": ["tts"]},
    "inworld": {"baseUrl": "https://api.inworld.ai", "validationType": "inworld", "serviceKinds": ["tts"]},
    "voyage-ai": {"baseUrl": "https://api.voyageai.com", "validationType": "voyage", "serviceKinds": ["embedding"]},
    "deepgram": {"baseUrl": "https://api.deepgram.com", "validationType": "deepgram", "serviceKinds": ["stt", "imageToText", "tts"]},

    "sdwebui": {"validationType": "noauth", "serviceKinds": ["image"]},
    "comfyui": {"validationType": "noauth", "serviceKinds": ["image"]},
    "bfl": {"baseUrl": "https://api.bfl.ai", "validationType": "openai", "serviceKinds": ["image"]},
    "replicate": {"baseUrl": "https://api.replicate.com", "validationType": "openai", "serviceKinds": ["image"]},
    "searxng": {"validationType": "noauth", "serviceKinds": ["webSearch"]},
    "firecrawl": {"baseUrl": "https://api.firecrawl.dev", "validationType": "openai", "serviceKinds": ["webFetch"]},
    "linkup": {"baseUrl": "https://api.linkup.so", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "searchapi": {"baseUrl": "https://www.searchapi.io", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "you-com": {"baseUrl": "https://api.you.com", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "crawl4ai": {"validationType": "noauth", "serviceKinds": ["webFetch"]},
    # ── Additional providers from original ──────────────────────────────
    "google-pse": {"baseUrl": "https://www.googleapis.com", "validationType": "openai", "serviceKinds": ["webSearch"]},
    "blackbox": {"baseUrl": "https://www.blackbox.ai", "validationType": "openai", "serviceKinds": ["llm"]},
    "commandcode": {"baseUrl": "https://api.commandcode.ai", "validationType": "openai", "serviceKinds": ["llm"]},
    "jina-reader": {"baseUrl": "https://r.jina.ai", "validationType": "openai", "serviceKinds": ["webFetch"]},
    "recraft": {"baseUrl": "https://external.api.recraft.ai", "validationType": "openai", "serviceKinds": ["image"]},
    "runwayml": {"baseUrl": "https://api.dev.runwayml.com", "validationType": "openai", "serviceKinds": ["image", "video"]},
    "topaz": {"baseUrl": "https://api.topazlabs.com", "validationType": "openai", "serviceKinds": ["image"]},
}

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
