"""Media providers API — providers filtered by service kind."""

from fastapi import APIRouter, HTTPException

from app.routers.providers.constants import PROVIDER_DEFAULTS

router = APIRouter(tags=["media-providers"])

# Provider display metadata (name, color, textIcon, mediaPriority)
# Ported from frontend constants/providers.js
PROVIDER_METADATA: dict[str, dict] = {
    "openai": {"name": "OpenAI", "color": "#10A37F", "textIcon": "OA", "mediaPriority": 2},
    "opencode-go": {"name": "OpenCode Go", "color": "#E87040", "textIcon": "OC"},
    "anthropic": {"name": "Anthropic", "color": "#D97757", "textIcon": "AC"},
    "askcodi": {"name": "AskCodi", "color": "#6366F1", "textIcon": "AC"},
    "google": {"name": "Google", "color": "#4285F4", "textIcon": "GO"},
    "gemini": {"name": "Gemini", "color": "#4285F4", "textIcon": "GE", "mediaPriority": 1},
    "openrouter": {"name": "OpenRouter", "color": "#F97316", "textIcon": "OR"},
    "deepseek": {"name": "DeepSeek", "color": "#0066FF", "textIcon": "DS"},
    "groq": {"name": "Groq", "color": "#F55036", "textIcon": "GQ"},
    "mistral": {"name": "Mistral", "color": "#FF7000", "textIcon": "MI"},
    "cohere": {"name": "Cohere", "color": "#39594D", "textIcon": "CO"},
    "fireworks": {"name": "Fireworks", "color": "#FF4F00", "textIcon": "FW"},
    "together": {"name": "Together", "color": "#6C3AED", "textIcon": "TG"},
    "xai": {"name": "xAI", "color": "#1DA1F2", "textIcon": "XA"},
    "cerebras": {"name": "Cerebras", "color": "#FF6B00", "textIcon": "CB"},
    "nebius": {"name": "Nebius", "color": "#000000", "textIcon": "NB"},
    "hyperbolic": {"name": "Hyperbolic", "color": "#7C3AED", "textIcon": "HB"},
    "perplexity": {"name": "Perplexity", "color": "#1A73E8", "textIcon": "PX"},
    "nvidia": {"name": "NVIDIA NIM", "color": "#76B900", "textIcon": "NV"},
    "siliconflow": {"name": "SiliconFlow", "color": "#000000", "textIcon": "SF"},
    "volcengine-ark": {"name": "Volcengine Ark", "color": "#1677FF", "textIcon": "ARK"},
    "volcengine": {"name": "Volcengine", "color": "#000000", "textIcon": "VK"},
    "byteplus": {"name": "BytePlus ModelArk", "color": "#2563EB", "textIcon": "BP"},
    "alicode": {"name": "Alibaba", "color": "#FF6A00", "textIcon": "ALi"},
    "alicode-intl": {"name": "Alibaba Intl", "color": "#FF6A00", "textIcon": "ALi"},
    "nanobanana": {"name": "NanoBanana", "color": "#FFD700", "textIcon": "NB"},
    "chutes": {"name": "Chutes", "color": "#000000", "textIcon": "CH"},
    "assemblyai": {"name": "AssemblyAI", "color": "#000000", "textIcon": "AI"},
    "vercel-ai-gateway": {"name": "Vercel AI Gateway", "color": "#000000", "textIcon": "VA"},
    "glm": {"name": "GLM Coding", "color": "#2563EB", "textIcon": "GL"},
    "kimi": {"name": "Kimi", "color": "#1E3A8A", "textIcon": "KM"},
    "minimax": {"name": "Minimax", "color": "#7C3AED", "textIcon": "MM"},
    "minimax-cn": {"name": "Minimax (China)", "color": "#DC2626", "textIcon": "MC"},
    "glm-cn": {"name": "GLM (China)", "color": "#DC2626", "textIcon": "GC"},
    "xiaomi-mimo": {"name": "Xiaomi MiMo", "color": "#FF6900", "textIcon": "XM"},
    "xiaomi-tokenplan": {"name": "Xiaomi MiMo (Token Plan)", "color": "#FF6700", "textIcon": "XT"},
    "huggingface": {"name": "Hugging Face", "color": "#FFD21E", "textIcon": "HF"},
    "azure": {"name": "Azure OpenAI", "color": "#0078D4", "textIcon": "AZ"},
    "vertex": {"name": "Vertex AI", "color": "#4285F4", "textIcon": "VX"},
    "vertex-partner": {"name": "Vertex Partner", "color": "#34A853", "textIcon": "VP"},
    "amazon-bedrock": {"name": "Amazon Bedrock", "color": "#FF9900", "textIcon": "AB"},
    "cloudflare-ai": {"name": "Cloudflare", "color": "#F38020", "textIcon": "CF"},
    "ollama": {"name": "Ollama Cloud", "color": "#FFFFFF", "textIcon": "OL"},
    "ollama-local": {"name": "Ollama Local", "color": "#FFFFFF", "textIcon": "OL"},
    "tavily": {"name": "Tavily", "color": "#5B21B6", "textIcon": "TV"},
    "brave-search": {"name": "Brave Search", "color": "#FB542B", "textIcon": "BR"},
    "serper": {"name": "Serper", "color": "#4F46E5", "textIcon": "SP"},
    "exa": {"name": "Exa", "color": "#2563EB", "textIcon": "EX"},
    "fal-ai": {"name": "Fal.ai", "color": "#2563EB", "textIcon": "FL"},
    "stability-ai": {"name": "Stability AI", "color": "#8B5CF6", "textIcon": "SA"},
    "jina-ai": {"name": "Jina AI", "color": "#2563EB", "textIcon": "JA"},
    "grok-web": {"name": "Grok Web", "color": "#1DA1F2", "textIcon": "GW"},
    "perplexity-web": {"name": "Perplexity Web", "color": "#20808D", "textIcon": "PW"},
    "kiro": {"name": "Kiro AI", "color": "#FF6B35", "textIcon": "KR"},
    "qwen": {"name": "Qwen Code", "color": "#10B981", "textIcon": "QW"},
    "gemini-cli": {"name": "Gemini CLI", "color": "#4285F4", "textIcon": "GC"},
    "iflow": {"name": "iFlow AI", "color": "#6366F1", "textIcon": "IF"},
    "opencode": {"name": "OpenCode Free", "color": "#E87040", "textIcon": "OC"},
    "claude": {"name": "Claude Code", "color": "#D97757", "textIcon": "CC"},
    "antigravity": {"name": "Antigravity", "color": "#F59E0B", "textIcon": "AG"},
    "codex": {"name": "OpenAI Codex", "color": "#3B82F6", "textIcon": "CX"},
    "github": {"name": "GitHub Copilot", "color": "#333333", "textIcon": "GH"},
    "cursor": {"name": "Cursor IDE", "color": "#00D4AA", "textIcon": "CU"},
    "kilocode": {"name": "Kilo Code", "color": "#FF6B35", "textIcon": "KC"},
    "kilo-gateway": {"name": "Kilo Gateway", "color": "#FF6B35", "textIcon": "KG"},
    "cline": {"name": "Cline", "color": "#5B9BD5", "textIcon": "CL"},
    # Media-only providers
    "elevenlabs": {"name": "ElevenLabs", "color": "#000000", "textIcon": "EL"},
    "cartesia": {"name": "Cartesia", "color": "#000000", "textIcon": "CA"},
    "playht": {"name": "PlayHT", "color": "#000000", "textIcon": "PH"},
    "local-device": {"name": "Local Device", "color": "#000000", "textIcon": "LD"},
    "google-tts": {"name": "Google TTS", "color": "#4285F4", "textIcon": "GT"},
    "edge-tts": {"name": "Edge TTS", "color": "#0078D4", "textIcon": "ET"},
    "coqui": {"name": "Coqui", "color": "#000000", "textIcon": "CQ"},
    "tortoise": {"name": "Tortoise TTS", "color": "#000000", "textIcon": "TT"},
    "inworld": {"name": "Inworld", "color": "#000000", "textIcon": "IW"},
    "voyage-ai": {"name": "Voyage AI", "color": "#000000", "textIcon": "VA"},
    "deepgram": {"name": "Deepgram", "color": "#000000", "textIcon": "DG"},
    "assemblyai-stt": {"name": "AssemblyAI STT", "color": "#000000", "textIcon": "AI"},
    "sdwebui": {"name": "SD WebUI", "color": "#000000", "textIcon": "SD"},
    "comfyui": {"name": "ComfyUI", "color": "#000000", "textIcon": "CU"},
    "bfl": {"name": "Black Forest Labs", "color": "#000000", "textIcon": "BF"},
    "replicate": {"name": "Replicate", "color": "#000000", "textIcon": "RP"},
    "searxng": {"name": "SearXNG", "color": "#000000", "textIcon": "SX"},
    "firecrawl": {"name": "Firecrawl", "color": "#000000", "textIcon": "FC"},
    "linkup": {"name": "Linkup", "color": "#000000", "textIcon": "LK"},
    "searchapi": {"name": "SearchAPI", "color": "#000000", "textIcon": "SA"},
    "you-com": {"name": "You.com", "color": "#000000", "textIcon": "YC"},
    "crawl4ai": {"name": "Crawl4AI", "color": "#000000", "textIcon": "C4"},
    "recraft": {"name": "Recraft", "color": "#EC4899", "textIcon": "RC"},
    "runwayml": {"name": "Runway ML", "color": "#000000", "textIcon": "RW"},
    "topaz": {"name": "Topaz", "color": "#059669", "textIcon": "TP"},
    "jina-reader": {"name": "Jina Reader", "color": "#000000", "textIcon": "JR"},
    "google-pse": {"name": "Google PSE", "color": "#4285F4", "textIcon": "GP"},
}

VALID_KINDS = {"embedding", "tts", "stt", "webSearch", "webFetch", "image", "imageToText", "video", "music"}


@router.get("/media-providers/{kind}")
async def list_media_providers(kind: str):
    """List providers that support a given service kind.

    Returns provider definitions (id, name, color, textIcon, serviceKinds)
    for use in the Media Providers page tabs.
    """
    if kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid kind '{kind}'. Valid: {', '.join(sorted(VALID_KINDS))}",
        )

    result = []
    for provider_id, defaults in PROVIDER_DEFAULTS.items():
        kinds = defaults.get("serviceKinds", ["llm"])
        if kind not in kinds:
            continue

        meta = PROVIDER_METADATA.get(provider_id, {})
        result.append({
            "id": provider_id,
            "name": meta.get("name", provider_id),
            "color": meta.get("color", "#888888"),
            "textIcon": meta.get("textIcon", provider_id[:2].upper()),
            "serviceKinds": kinds,
            "mediaPriority": meta.get("mediaPriority", 100),
        })

    # Sort by mediaPriority (lower = higher priority)
    result.sort(key=lambda x: x.get("mediaPriority", 100))
    return result


@router.get("/media-providers")
async def list_all_media_providers():
    """List all media providers grouped by kind.

    Returns a dict with kind keys mapping to provider lists.
    """
    result: dict[str, list] = {}

    for kind in sorted(VALID_KINDS):
        providers = []
        for provider_id, defaults in PROVIDER_DEFAULTS.items():
            kinds = defaults.get("serviceKinds", ["llm"])
            if kind not in kinds:
                continue

            meta = PROVIDER_METADATA.get(provider_id, {})
            providers.append({
                "id": provider_id,
                "name": meta.get("name", provider_id),
                "color": meta.get("color", "#888888"),
                "textIcon": meta.get("textIcon", provider_id[:2].upper()),
                "serviceKinds": kinds,
                "mediaPriority": meta.get("mediaPriority", 100),
            })

        providers.sort(key=lambda x: x.get("mediaPriority", 100))
        result[kind] = providers

    return result
