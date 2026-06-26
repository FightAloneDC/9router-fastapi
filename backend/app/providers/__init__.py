"""Provider package.

Each provider lives in its own sub-package (e.g. providers/cerebras/).
All provider name references MUST use constants below — never string literals.
"""

# ── Provider constants ─────────────────────────────────────────────────────
# Free tier providers
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_NVIDIA = "nvidia"
PROVIDER_OLLAMA = "ollama"
PROVIDER_VERTEX = "vertex"
PROVIDER_GEMINI = "gemini"
PROVIDER_CLOUDFLARE_AI = "cloudflare-ai"
PROVIDER_BYTEPLUS = "byteplus"

# LLM providers (API key)
PROVIDER_CEREBRAS = "cerebras"
PROVIDER_GROQ = "groq"
PROVIDER_OPENAI = "openai"
PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_XAI = "xai"
PROVIDER_MISTRAL = "mistral"
PROVIDER_PERPLEXITY = "perplexity"
PROVIDER_TOGETHER = "together"
PROVIDER_FIREWORKS = "fireworks"
PROVIDER_COHERE = "cohere"
PROVIDER_NEBIUS = "nebius"
PROVIDER_SILICONFLOW = "siliconflow"
PROVIDER_HYPERBOLIC = "hyperbolic"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GLM = "glm"
PROVIDER_GLM_CN = "glm-cn"
PROVIDER_ALICODE = "alicode"
PROVIDER_ALICODE_INTL = "alicode-intl"
PROVIDER_MINIMAX = "minimax"
PROVIDER_MINIMAX_CN = "minimax-cn"
PROVIDER_KIMI = "kimi"
PROVIDER_VOLCENGINE_ARK = "volcengine-ark"
PROVIDER_VOLCENGINE = "volcengine"
PROVIDER_XIAOMI_MIMO = "xiaomi-mimo"
PROVIDER_XIAOMI_TOKENPLAN = "xiaomi-tokenplan"
PROVIDER_BLACKBOX = "blackbox"
PROVIDER_COMMANDCODE = "commandcode"
PROVIDER_KILO_GATEWAY = "kilo-gateway"
PROVIDER_OPENCODE = "opencode"
PROVIDER_OPENCODE_GO = "opencode-go"
PROVIDER_VERCEL_AI_GATEWAY = "vercel-ai-gateway"
PROVIDER_ASKCODI = "askcodi"
PROVIDER_VERTEX_PARTNER = "vertex-partner"
PROVIDER_ASSEMBLYAI = "assemblyai"
PROVIDER_NANOBANANA = "nanobanana"

# Embedding providers
PROVIDER_JINA_AI = "jina-ai"
PROVIDER_VOYAGE_AI = "voyage-ai"

# Search providers
PROVIDER_TAVILY = "tavily"
PROVIDER_BRAVE_SEARCH = "brave-search"
PROVIDER_SERPER = "serper"
PROVIDER_EXA = "exa"
PROVIDER_SEARXNG = "searxng"
PROVIDER_LINKUP = "linkup"
PROVIDER_SEARCHAPI = "searchapi"
PROVIDER_YOU_COM = "you-com"
PROVIDER_GOOGLE_PSE = "google-pse"

# Web fetch providers
PROVIDER_FIRECRAWL = "firecrawl"
PROVIDER_CRAWL4AI = "crawl4ai"
PROVIDER_JINA_READER = "jina-reader"

# Image providers
PROVIDER_FAL_AI = "fal-ai"
PROVIDER_STABILITY_AI = "stability-ai"
PROVIDER_REPLICATE = "replicate"
PROVIDER_BFL = "bfl"
PROVIDER_COMFYUI = "comfyui"
PROVIDER_RECRAFT = "recraft"
PROVIDER_RUNWAYML = "runwayml"
PROVIDER_TOPAZ = "topaz"
PROVIDER_SDWEBUI = "sdwebui"
PROVIDER_HUGGINGFACE = "huggingface"

# TTS/STT providers
PROVIDER_ELEVENLABS = "elevenlabs"
PROVIDER_DEEPGRAM = "deepgram"
PROVIDER_INWORLD = "inworld"
PROVIDER_CARTESIA = "cartesia"
PROVIDER_PLAYHT = "playht"
PROVIDER_GOOGLE_TTS = "google-tts"
PROVIDER_COQUI = "coqui"
PROVIDER_EDGE_TTS = "edge-tts"
PROVIDER_LOCAL_DEVICE = "local-device"
PROVIDER_TORTOISE = "tortoise"

# Special providers (provider-specific data / local)
PROVIDER_AZURE = "azure"
PROVIDER_AMAZON_BEDROCK = "amazon-bedrock"
PROVIDER_OLLAMA_LOCAL = "ollama-local"

# Special providers (complex auth)
PROVIDER_QODER = "qoder"
PROVIDER_CLAUDE = "claude"
PROVIDER_CODEX = "codex"
PROVIDER_GEMINI_CLI = "gemini-cli"
PROVIDER_ANTIGRAVITY = "antigravity"
PROVIDER_IFLOW = "iflow"
PROVIDER_GITHUB = "github"
PROVIDER_GITLAB = "gitlab"
PROVIDER_QWEN = "qwen"
PROVIDER_KIRO = "kiro"
PROVIDER_CURSOR = "cursor"
PROVIDER_KIMI_CODING = "kimi-coding"
PROVIDER_KILOCODE = "kilocode"
PROVIDER_CLINE = "cline"
PROVIDER_CODEBUDDY = "codebuddy"

# ── All implemented providers ──────────────────────────────────────────────
AVAILABLE_PROVIDERS: list[str] = [
    # Free tier
    PROVIDER_OPENROUTER,
    PROVIDER_NVIDIA,
    PROVIDER_OLLAMA,
    PROVIDER_VERTEX,
    PROVIDER_GEMINI,
    PROVIDER_BYTEPLUS,
    # LLM
    PROVIDER_CEREBRAS,
    PROVIDER_GROQ,
    PROVIDER_OPENAI,
    PROVIDER_DEEPSEEK,
    PROVIDER_XAI,
    PROVIDER_MISTRAL,
    PROVIDER_PERPLEXITY,
    PROVIDER_TOGETHER,
    PROVIDER_FIREWORKS,
    PROVIDER_COHERE,
    PROVIDER_NEBIUS,
    PROVIDER_SILICONFLOW,
    PROVIDER_HYPERBOLIC,
    PROVIDER_ANTHROPIC,
    PROVIDER_GLM,
    PROVIDER_GLM_CN,
    PROVIDER_ALICODE,
    PROVIDER_ALICODE_INTL,
    PROVIDER_MINIMAX,
    PROVIDER_MINIMAX_CN,
    PROVIDER_KIMI,
    PROVIDER_VOLCENGINE_ARK,
    PROVIDER_VOLCENGINE,
    PROVIDER_XIAOMI_MIMO,
    PROVIDER_XIAOMI_TOKENPLAN,
    PROVIDER_BLACKBOX,
    PROVIDER_COMMANDCODE,
    PROVIDER_KILO_GATEWAY,
    PROVIDER_KILOCODE,
    PROVIDER_OPENCODE,
    PROVIDER_OPENCODE_GO,
    PROVIDER_VERCEL_AI_GATEWAY,
    PROVIDER_ASKCODI,
    PROVIDER_VERTEX_PARTNER,
    PROVIDER_ASSEMBLYAI,
    PROVIDER_NANOBANANA,
    # Embedding
    PROVIDER_JINA_AI,
    PROVIDER_VOYAGE_AI,
    # Search
    PROVIDER_TAVILY,
    PROVIDER_BRAVE_SEARCH,
    PROVIDER_SERPER,
    PROVIDER_EXA,
    PROVIDER_SEARXNG,
    PROVIDER_LINKUP,
    PROVIDER_SEARCHAPI,
    PROVIDER_YOU_COM,
    PROVIDER_GOOGLE_PSE,
    # Web fetch
    PROVIDER_FIRECRAWL,
    PROVIDER_CRAWL4AI,
    PROVIDER_JINA_READER,
    # Image
    PROVIDER_FAL_AI,
    PROVIDER_STABILITY_AI,
    PROVIDER_REPLICATE,
    PROVIDER_BFL,
    PROVIDER_COMFYUI,
    PROVIDER_RECRAFT,
    PROVIDER_RUNWAYML,
    PROVIDER_TOPAZ,
    PROVIDER_SDWEBUI,
    PROVIDER_HUGGINGFACE,
    # TTS/STT
    PROVIDER_ELEVENLABS,
    PROVIDER_DEEPGRAM,
    PROVIDER_INWORLD,
    PROVIDER_CARTESIA,
    PROVIDER_PLAYHT,
    PROVIDER_GOOGLE_TTS,
    PROVIDER_COQUI,
    PROVIDER_EDGE_TTS,
    PROVIDER_LOCAL_DEVICE,
    PROVIDER_TORTOISE,
    PROVIDER_AZURE,
    PROVIDER_AMAZON_BEDROCK,
    PROVIDER_CLOUDFLARE_AI,
    PROVIDER_OLLAMA_LOCAL,
    PROVIDER_QODER,
]


# ── Model type overrides aggregator ──────────────────────────────────────
def get_all_model_type_overrides() -> dict[str, str]:
    """Aggregate MODEL_TYPE_OVERRIDES from all providers.

    Each provider can define MODEL_TYPE_OVERRIDES in its config to map
    model_id → type (e.g. "whisper-1" → "stt"). This function collects
    all overrides into a single dict.
    """
    from app.providers.provider import Provider

    overrides: dict[str, str] = {}
    for name in AVAILABLE_PROVIDERS:
        try:
            p = Provider(name)
            config = p.config()
            if hasattr(config, "MODEL_TYPE_OVERRIDES") and config.MODEL_TYPE_OVERRIDES:
                overrides.update(config.MODEL_TYPE_OVERRIDES)
        except (ValueError, ModuleNotFoundError):
            pass
    return overrides
