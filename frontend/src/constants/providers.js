// Provider definitions — ported from original Next.js shared/constants/providers.js
// Categories: FREE_PROVIDERS, FREE_TIER_PROVIDERS, OAUTH_PROVIDERS, APIKEY_PROVIDERS, WEB_COOKIE_PROVIDERS

const RISK_NOTICE = "⚠️ Risk Notice: This provider uses a subscription/OAuth session not officially licensed for proxy/router use. Account may be restricted or banned. Use at your own risk.";

// ── Thinking Config ────────────────────────────────────────────────────────
export const THINKING_CONFIG = {
  extended: {
    options: ["auto", "on", "off"],
    defaultMode: "auto",
    defaultBudgetTokens: 10000,
  },
  effort: {
    options: ["auto", "none", "low", "medium", "high"],
    defaultMode: "auto",
  },
};

// ── Free Providers ─────────────────────────────────────────────────────────
export const FREE_PROVIDERS = {
  kiro: { id: "kiro", alias: "kr", name: "Kiro AI", icon: "Brain", color: "#FF6B35", textIcon: "KR", deprecated: true, deprecationNotice: RISK_NOTICE, website: "https://kiro.dev", notice: { signupUrl: "https://kiro.dev" }, serviceKinds: ["llm", "tts"] },
  qwen: { id: "qwen", alias: "qw", name: "Qwen Code", icon: "Brain", color: "#10B981", textIcon: "QW", mediaPriority: 999, hidden: true, deprecated: true, deprecationNotice: "Qwen OAuth free tier was discontinued by Alibaba on 2026-04-15. New connections will not work.", website: "https://chat.qwen.ai", notice: { signupUrl: "https://chat.qwen.ai" }, serviceKinds: ["llm"] },
  "gemini-cli": { id: "gemini-cli", alias: "gc", name: "Gemini CLI", icon: "Terminal", color: "#4285F4", textIcon: "GC", deprecated: true, deprecationNotice: RISK_NOTICE, website: "https://github.com/google-gemini/gemini-cli", notice: { signupUrl: "https://github.com/google-gemini/gemini-cli" } },
  iflow: { id: "iflow", alias: "if", name: "iFlow AI", icon: "Droplets", color: "#6366F1", textIcon: "IF", hidden: true, website: "https://iflow.cn", notice: { signupUrl: "https://iflow.cn" } },
  opencode: { id: "opencode", alias: "oc", name: "OpenCode Free", icon: "Terminal", color: "#E87040", textIcon: "OC", noAuth: true, passthroughModels: true, modelsFetcher: { url: "https://opencode.ai/zen/v1/models", type: "opencode-free" } },
};

// ── Free Tier Providers ────────────────────────────────────────────────────
export const FREE_TIER_PROVIDERS = {
  openrouter: { id: "openrouter", alias: "openrouter", name: "OpenRouter", icon: "Router", color: "#F97316", textIcon: "OR", website: "https://openrouter.ai", notice: { text: "Free tier: 27+ free models, no credit card needed, 200 req/day.", apiKeyUrl: "https://openrouter.ai/settings/keys" }, serviceKinds: ["llm", "embedding", "imageToText", "tts"] },
  nvidia: { id: "nvidia", alias: "nvidia", name: "NVIDIA NIM", icon: "Cpu", color: "#76B900", textIcon: "NV", website: "https://developer.nvidia.com/nim", notice: { text: "Free access for NVIDIA Developer Program members.", apiKeyUrl: "https://build.nvidia.com/settings/api-keys" }, serviceKinds: ["llm", "tts", "embedding"] },
  ollama: { id: "ollama", alias: "ollama", name: "Ollama Cloud", icon: "Cloud", color: "#FFFFFF", textIcon: "OL", website: "https://ollama.com", notice: { text: "Free tier: light usage, 1 cloud model at a time.", apiKeyUrl: "https://ollama.com/settings/keys" } },
  vertex: { id: "vertex", alias: "vx", name: "Vertex AI", icon: "Cloud", color: "#4285F4", textIcon: "VX", website: "https://cloud.google.com/vertex-ai", notice: { text: "New Google Cloud accounts get $300 free credits.", apiKeyUrl: "https://console.cloud.google.com/iam-admin/serviceaccounts" } },
  gemini: { id: "gemini", alias: "gemini", name: "Gemini", icon: "Diamond", color: "#4285F4", textIcon: "GE", mediaPriority: 1, website: "https://ai.google.dev", notice: { apiKeyUrl: "https://aistudio.google.com/app/apikey" }, serviceKinds: ["llm", "embedding", "image", "imageToText", "webSearch", "tts", "stt"] },
  "cloudflare-ai": { id: "cloudflare-ai", alias: "cf", name: "Cloudflare", icon: "Cloud", color: "#F38020", textIcon: "CF", website: "https://developers.cloudflare.com/workers-ai/", notice: { text: "Workers AI free tier.", apiKeyUrl: "https://dash.cloudflare.com/profile/api-tokens" }, serviceKinds: ["llm", "image"], hasProviderSpecificData: true },
  byteplus: { id: "byteplus", alias: "bpm", name: "BytePlus ModelArk", icon: "Cloud", color: "#2563EB", textIcon: "BP", website: "https://console.byteplus.com/ark", notice: { text: "Free credits for new accounts.", apiKeyUrl: "https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey" }, serviceKinds: ["llm"] },
};

// ── OAuth Providers ────────────────────────────────────────────────────────
export const OAUTH_PROVIDERS = {
  claude: { id: "claude", alias: "cc", name: "Claude Code", icon: "Bot", color: "#D97757", textIcon: "CC", deprecated: true, deprecationNotice: RISK_NOTICE, website: "https://claude.ai", notice: { signupUrl: "https://claude.ai" } },
  antigravity: { id: "antigravity", alias: "ag", name: "Antigravity", icon: "Rocket", color: "#F59E0B", textIcon: "AG", hidden: true, deprecated: true, deprecationNotice: "AG is designed exclusively for Antigravity IDE.", website: "https://antigravity.google", notice: { signupUrl: "https://antigravity.google" } },
  codex: { id: "codex", alias: "cx", name: "OpenAI Codex", icon: "Code", color: "#3B82F6", textIcon: "CX", deprecated: true, deprecationNotice: RISK_NOTICE, thinkingConfig: THINKING_CONFIG.effort, serviceKinds: ["llm", "image"], website: "https://chatgpt.com/codex", notice: { signupUrl: "https://chatgpt.com/codex" } },
  github: { id: "github", alias: "gh", name: "GitHub Copilot", icon: "Code", color: "#333333", textIcon: "GH", deprecated: true, deprecationNotice: RISK_NOTICE, serviceKinds: ["llm", "embedding"], website: "https://github.com/features/copilot", notice: { signupUrl: "https://github.com/features/copilot" } },
  cursor: { id: "cursor", alias: "cu", name: "Cursor IDE", icon: "PenLine", color: "#00D4AA", textIcon: "CU", website: "https://cursor.com", notice: { signupUrl: "https://cursor.com" } },
  kilocode: { id: "kilocode", alias: "kilo", name: "Kilo Code", icon: "Code", color: "#FF6B35", textIcon: "KC", website: "https://kilocode.ai", notice: { signupUrl: "https://kilocode.ai" } },
  cline: { id: "cline", alias: "cl", name: "Cline", icon: "Bot", color: "#5B9BD5", textIcon: "CL", website: "https://cline.bot", notice: { signupUrl: "https://cline.bot" } },
  qoder: { id: "qoder", alias: "qd", name: "Qoder", icon: "Zap", color: "#8B5CF6", textIcon: "QD", website: "https://qoder.com", notice: { signupUrl: "https://qoder.com" }, serviceKinds: ["llm"] },
};

// ── API Key Providers ──────────────────────────────────────────────────────
export const APIKEY_PROVIDERS = {
  glm: { id: "glm", alias: "glm", name: "GLM Coding", icon: "Code", color: "#2563EB", textIcon: "GL", website: "https://open.bigmodel.cn", notice: { apiKeyUrl: "https://open.bigmodel.cn/usercenter/apikeys" } },
  "glm-cn": { id: "glm-cn", alias: "glm-cn", name: "GLM (China)", icon: "Code", color: "#DC2626", textIcon: "GC", website: "https://open.bigmodel.cn", notice: { apiKeyUrl: "https://open.bigmodel.cn/usercenter/apikeys" } },
  kimi: { id: "kimi", alias: "kimi", name: "Kimi", icon: "Brain", color: "#1E3A8A", textIcon: "KM", website: "https://kimi.moonshot.cn", notice: { apiKeyUrl: "https://platform.moonshot.ai/console/api-keys" }, serviceKinds: ["llm", "webSearch"] },
  minimax: { id: "minimax", alias: "minimax", name: "Minimax Coding", icon: "MemoryStick", color: "#7C3AED", textIcon: "MM", website: "https://www.minimaxi.com", notice: { apiKeyUrl: "https://platform.minimaxi.com/user-center/basic-information/interface-key" }, serviceKinds: ["llm", "image", "imageToText", "webSearch", "tts"] },
  "minimax-cn": { id: "minimax-cn", alias: "minimax-cn", name: "Minimax (China)", icon: "MemoryStick", color: "#DC2626", textIcon: "MC", website: "https://www.minimaxi.com", notice: { apiKeyUrl: "https://platform.minimaxi.com/user-center/basic-information/interface-key" }, serviceKinds: ["llm", "tts"] },
  alicode: { id: "alicode", alias: "alicode", name: "Alibaba", icon: "Cloud", color: "#FF6A00", textIcon: "ALi", website: "https://bailian.console.aliyun.com", notice: { apiKeyUrl: "https://bailian.console.aliyun.com/?apiKey=***" } },
  "alicode-intl": { id: "alicode-intl", alias: "alicode-intl", name: "Alibaba Intl", icon: "Cloud", color: "#FF6A00", textIcon: "ALi", website: "https://modelstudio.console.alibabacloud.com", notice: { apiKeyUrl: "https://modelstudio.console.alibabacloud.com/?apiKey=***" } },
  "xiaomi-mimo": { id: "xiaomi-mimo", alias: "mimo", name: "Xiaomi MiMo", icon: "Bot", color: "#FF6900", textIcon: "XM", website: "https://xiaomimimo.com", notice: { apiKeyUrl: "https://xiaomimimo.com" } },
  "xiaomi-tokenplan": { id: "xiaomi-tokenplan", alias: "xmtp", name: "Xiaomi MiMo (Token Plan)", icon: "Bot", color: "#FF6700", textIcon: "XT", website: "https://mimo.xiaomi.com", notice: { text: "Xiaomi MiMo Token Plan subscription.", apiKeyUrl: "https://mimo.xiaomi.com" }, hasProviderSpecificData: true, regions: [{ id: "sgp", label: "Singapore" }, { id: "cn", label: "China" }, { id: "ams", label: "Europe" }], defaultRegion: "sgp" },
  "volcengine-ark": { id: "volcengine-ark", alias: "ark", name: "Volcengine Ark", icon: "Cloud", color: "#1677FF", textIcon: "ARK", website: "https://ark.cn-beijing.volces.com", notice: { apiKeyUrl: "https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey" } },
  openai: { id: "openai", alias: "openai", name: "OpenAI", icon: "Sparkles", color: "#10A37F", textIcon: "OA", website: "https://platform.openai.com", notice: { apiKeyUrl: "https://platform.openai.com/api-keys" }, serviceKinds: ["llm", "embedding", "tts", "stt", "image", "imageToText", "webSearch"], thinkingConfig: THINKING_CONFIG.effort },
  "opencode-go": { id: "opencode-go", alias: "ocg", name: "OpenCode Go", icon: "Terminal", color: "#E87040", textIcon: "OC", website: "https://opencode.ai/auth", notice: { text: "OpenCode Go subscription: $5/mo (then $10/mo). Access to Kimi, GLM, Qwen, MiMo, MiniMax models.", apiKeyUrl: "https://opencode.ai/auth" }, serviceKinds: ["llm"] },
  "vercel-ai-gateway": { id: "vercel-ai-gateway", alias: "vag", name: "Vercel AI Gateway", icon: "Triangle", color: "#000000", textIcon: "VA", website: "https://vercel.com/docs/ai-gateway", notice: { apiKeyUrl: "https://vercel.com/dashboard" }, serviceKinds: ["llm"] },
  deepseek: { id: "deepseek", alias: "ds", name: "DeepSeek", icon: "Sparkles", color: "#0066FF", textIcon: "DS", website: "https://platform.deepseek.com", notice: { apiKeyUrl: "https://platform.deepseek.com/api_keys" }, serviceKinds: ["llm"] },
  groq: { id: "groq", alias: "gq", name: "Groq", icon: "Zap", color: "#F55036", textIcon: "GQ", website: "https://console.groq.com", notice: { apiKeyUrl: "https://console.groq.com/keys" }, serviceKinds: ["llm", "imageToText", "stt"] },
  mistral: { id: "mistral", alias: "mi", name: "Mistral", icon: "Wind", color: "#FF7000", textIcon: "MI", website: "https://console.mistral.ai", notice: { apiKeyUrl: "https://console.mistral.ai/api-keys/" }, serviceKinds: ["llm", "imageToText", "embedding"] },
  together: { id: "together", alias: "tg", name: "Together", icon: "Layers", color: "#6C3AED", textIcon: "TG", website: "https://api.together.xyz", notice: { apiKeyUrl: "https://api.together.xyz/settings/api-keys" }, serviceKinds: ["llm", "embedding"] },
  fireworks: { id: "fireworks", alias: "fw", name: "Fireworks", icon: "Flame", color: "#FF4F00", textIcon: "FW", website: "https://fireworks.ai", notice: { apiKeyUrl: "https://fireworks.ai/account/api-keys" }, serviceKinds: ["llm", "embedding"] },
  perplexity: { id: "perplexity", alias: "px", name: "Perplexity", icon: "Search", color: "#1A73E8", textIcon: "PX", website: "https://www.perplexity.ai", notice: { apiKeyUrl: "https://www.perplexity.ai/settings/api" }, serviceKinds: ["llm", "webSearch"] },
  cohere: { id: "cohere", alias: "co", name: "Cohere", icon: "Sparkles", color: "#39594D", textIcon: "CO", website: "https://dashboard.cohere.com", notice: { apiKeyUrl: "https://dashboard.cohere.com/api-keys" }, serviceKinds: ["llm", "embedding"] },
  cerebras: { id: "cerebras", alias: "cb", name: "Cerebras", icon: "Cpu", color: "#FF6B00", textIcon: "CB", website: "https://cloud.cerebras.ai", notice: { apiKeyUrl: "https://cloud.cerebras.ai/" }, serviceKinds: ["llm"] },
  huggingface: { id: "huggingface", alias: "hf", name: "Hugging Face", icon: "Box", color: "#FFD21E", textIcon: "HF", website: "https://huggingface.co", notice: { apiKeyUrl: "https://huggingface.co/settings/tokens" }, serviceKinds: ["image", "imageToText", "stt", "tts"] },
  siliconflow: { id: "siliconflow", alias: "sf", name: "SiliconFlow", icon: "Cpu", color: "#000000", textIcon: "SF", website: "https://cloud.siliconflow.com", notice: { apiKeyUrl: "https://cloud.siliconflow.com/account/ak" }, serviceKinds: ["llm", "embedding", "image", "tts"] },
  anthropic: { id: "anthropic", alias: "an", name: "Anthropic", icon: "Bot", color: "#D97757", textIcon: "AC", website: "https://console.anthropic.com", notice: { apiKeyUrl: "https://console.anthropic.com/settings/keys" }, serviceKinds: ["llm", "imageToText"] },
  askcodi: { id: "askcodi", alias: "ac", name: "AskCodi", icon: "Code", color: "#6366F1", textIcon: "AC", website: "https://www.askcodi.com/", notice: { text: "Free tier: 100K token free credit on signup.", apiKeyUrl: "https://www.askcodi.com/api_keys" }, serviceKinds: ["llm"] },
  azure: { id: "azure", alias: "az", name: "Azure OpenAI", icon: "Cloud", color: "#0078D4", textIcon: "AZ", website: "https://azure.microsoft.com", serviceKinds: ["llm"], hasProviderSpecificData: true },
  "amazon-bedrock": { id: "amazon-bedrock", alias: "bedrock", name: "Amazon Bedrock", icon: "Cloud", color: "#FF9900", textIcon: "AB", website: "https://aws.amazon.com/bedrock/", serviceKinds: ["llm"], hasProviderSpecificData: true },
  xai: { id: "xai", alias: "xai", name: "xAI", icon: "Sparkles", color: "#1DA1F2", textIcon: "XA", website: "https://console.x.ai", notice: { apiKeyUrl: "https://console.x.ai/" }, serviceKinds: ["llm", "imageToText", "webSearch"] },
  "ollama-local": { id: "ollama-local", alias: "ollama-local", name: "Ollama Local", icon: "Cloud", color: "#FFFFFF", textIcon: "OL", website: "https://ollama.com" },
  "vertex-partner": { id: "vertex-partner", alias: "vxp", name: "Vertex Partner", icon: "Cloud", color: "#34A853", textIcon: "VP", website: "https://cloud.google.com/vertex-ai" },
  volcengine: { id: "volcengine", alias: "vk", name: "Volcengine Ark", icon: "Cloud", color: "#000000", textIcon: "VK", serviceKinds: ["llm"] },
  tavily: { id: "tavily", alias: "tavily", name: "Tavily", icon: "Search", color: "#5B21B6", textIcon: "TV", website: "https://tavily.com", notice: { apiKeyUrl: "https://app.tavily.com/home" }, serviceKinds: ["webSearch", "webFetch"] },
  "brave-search": { id: "brave-search", alias: "brave", name: "Brave Search", icon: "Globe", color: "#FB542B", textIcon: "BR", website: "https://brave.com/search/api", notice: { apiKeyUrl: "https://api-dashboard.search.brave.com/app/keys" }, serviceKinds: ["webSearch"] },
  serper: { id: "serper", alias: "serper", name: "Serper", icon: "Search", color: "#4F46E5", textIcon: "SP", website: "https://serper.dev", notice: { apiKeyUrl: "https://serper.dev/api-key" }, serviceKinds: ["webSearch"] },
  exa: { id: "exa", alias: "exa", name: "Exa", icon: "Search", color: "#2563EB", textIcon: "EX", website: "https://exa.ai", notice: { apiKeyUrl: "https://dashboard.exa.ai/api-keys" }, serviceKinds: ["webSearch", "webFetch"] },
  "fal-ai": { id: "fal-ai", alias: "fal", name: "Fal.ai", icon: "Image", color: "#2563EB", textIcon: "FL", website: "https://fal.ai", notice: { apiKeyUrl: "https://fal.ai/dashboard/keys" }, serviceKinds: ["image"] },
  "stability-ai": { id: "stability-ai", alias: "stability", name: "Stability AI", icon: "Image", color: "#8B5CF6", textIcon: "SA", website: "https://stability.ai", notice: { apiKeyUrl: "https://platform.stability.ai/account/keys" }, serviceKinds: ["image"] },
  "jina-ai": { id: "jina-ai", alias: "jina", name: "Jina AI", icon: "Layers", color: "#2563EB", textIcon: "JA", website: "https://jina.ai", notice: { text: "10M free tokens on signup.", apiKeyUrl: "https://jina.ai/?sui=apikey" }, serviceKinds: ["embedding"] },
  "kilo-gateway": { id: "kilo-gateway", alias: "kilo", name: "Kilo Gateway", icon: "Code", color: "#FF6B35", textIcon: "KG", website: "https://kilo.ai", notice: { apiKeyUrl: "https://kilo.ai" }, serviceKinds: ["llm"] },
  "nebius": { id: "nebius", alias: "nb", name: "Nebius AI", icon: "Cloud", color: "#00A3FF", textIcon: "NB", website: "https://nebius.ai", notice: { apiKeyUrl: "https://studio.nebius.ai/settings/api-keys" }, serviceKinds: ["llm", "embedding"] },
  "voyage-ai": { id: "voyage-ai", alias: "voyage", name: "Voyage AI", icon: "Compass", color: "#FF6B6B", textIcon: "VY", website: "https://www.voyageai.com", notice: { apiKeyUrl: "https://dash.voyageai.com/api-keys" }, serviceKinds: ["embedding"] },
  "elevenlabs": { id: "elevenlabs", alias: "el", name: "ElevenLabs", icon: "Volume2", color: "#000000", textIcon: "EL", website: "https://elevenlabs.io", notice: { apiKeyUrl: "https://elevenlabs.io/app/settings/api-keys" }, serviceKinds: ["tts"] },
  "deepgram": { id: "deepgram", alias: "dg", name: "Deepgram", icon: "Mic", color: "#13EF93", textIcon: "DG", website: "https://deepgram.com", notice: { apiKeyUrl: "https://console.deepgram.com/product/api-keys" }, serviceKinds: ["tts", "stt"] },
  "inworld": { id: "inworld", alias: "iw", name: "Inworld AI", icon: "Bot", color: "#7C3AED", textIcon: "IW", website: "https://inworld.ai", notice: { apiKeyUrl: "https://studio.inworld.ai" }, serviceKinds: ["tts"] },
  "cartesia": { id: "cartesia", alias: "cart", name: "Cartesia", icon: "AudioLines", color: "#06B6D4", textIcon: "CA", website: "https://cartesia.ai", notice: { apiKeyUrl: "https://play.cartesia.ai/keys" }, serviceKinds: ["tts"] },
  "playht": { id: "playht", alias: "pht", name: "PlayHT", icon: "Play", color: "#F59E0B", textIcon: "PH", website: "https://play.ht", notice: { apiKeyUrl: "https://play.ht/studio/api-access" }, serviceKinds: ["tts"] },
  "edge-tts": { id: "edge-tts", alias: "edge", name: "Edge TTS", icon: "Volume2", color: "#0078D4", textIcon: "ET", noAuth: true, website: "https://www.microsoft.com/edge", serviceKinds: ["tts"] },
  "local-device": { id: "local-device", alias: "local", name: "Local Device", icon: "Speaker", color: "#6B7280", textIcon: "LD", noAuth: true, website: "https://espeak.sourceforge.net", serviceKinds: ["tts"] },
  "assemblyai": { id: "assemblyai", alias: "aai", name: "AssemblyAI", icon: "Mic", color: "#0F172A", textIcon: "AA", website: "https://www.assemblyai.com", notice: { apiKeyUrl: "https://www.assemblyai.com/app" }, serviceKinds: ["stt"] },
  "hyperbolic": { id: "hyperbolic", alias: "hyp", name: "Hyperbolic", icon: "Zap", color: "#8B5CF6", textIcon: "HY", website: "https://hyperbolic.xyz", notice: { apiKeyUrl: "https://app.hyperbolic.xyz/settings" }, serviceKinds: ["tts"] },
  "coqui": { id: "coqui", alias: "cq", name: "Coqui TTS", icon: "AudioLines", color: "#10B981", textIcon: "CQ", website: "https://coqui.ai", notice: { apiKeyUrl: "https://coqui.ai" }, serviceKinds: ["tts"] },
  "google-tts": { id: "google-tts", alias: "gtts", name: "Google TTS", icon: "Volume2", color: "#4285F4", textIcon: "GT", website: "https://cloud.google.com/text-to-speech", notice: { apiKeyUrl: "https://console.cloud.google.com/apis/credentials" }, serviceKinds: ["tts"] },
  "tortoise": { id: "tortoise", alias: "tt", name: "Tortoise TTS", icon: "AudioLines", color: "#6B7280", textIcon: "TT", noAuth: true, website: "https://github.com/neonbjb/tortoise-tts", serviceKinds: ["tts"] },
  "searxng": { id: "searxng", alias: "sx", name: "SearXNG", icon: "Search", color: "#FF6B35", textIcon: "SX", website: "https://searxng.org", notice: { text: "Self-hosted metasearch engine." }, serviceKinds: ["webSearch"] },
  "linkup": { id: "linkup", alias: "lk", name: "Linkup", icon: "Search", color: "#3B82F6", textIcon: "LK", website: "https://linkup.so", notice: { apiKeyUrl: "https://linkup.so/dashboard" }, serviceKinds: ["webSearch"] },
  "searchapi": { id: "searchapi", alias: "sapi", name: "SearchAPI", icon: "Search", color: "#10B981", textIcon: "SA", website: "https://www.searchapi.io", notice: { apiKeyUrl: "https://www.searchapi.io/dashboard" }, serviceKinds: ["webSearch"] },
  "you-com": { id: "you-com", alias: "you", name: "You.com", icon: "Search", color: "#8B5CF6", textIcon: "YC", website: "https://api.you.com", notice: { apiKeyUrl: "https://api.you.com/dashboard" }, serviceKinds: ["webSearch"] },
  "firecrawl": { id: "firecrawl", alias: "fc", name: "Firecrawl", icon: "Globe", color: "#F97316", textIcon: "FC", website: "https://firecrawl.dev", notice: { apiKeyUrl: "https://firecrawl.dev/app/api-keys" }, serviceKinds: ["webFetch"] },
  "crawl4ai": { id: "crawl4ai", alias: "c4ai", name: "Crawl4AI", icon: "Globe", color: "#06B6D4", textIcon: "C4", website: "https://crawl4ai.com", notice: { text: "Open-source web crawling." }, serviceKinds: ["webFetch"] },
  "sdwebui": { id: "sdwebui", alias: "sd", name: "Stable Diffusion WebUI", icon: "Image", color: "#A855F7", textIcon: "SD", website: "https://github.com/AUTOMATIC1111/stable-diffusion-webui", notice: { text: "Local Stable Diffusion WebUI." }, serviceKinds: ["image"] },
  "replicate": { id: "replicate", alias: "rep", name: "Replicate", icon: "Image", color: "#000000", textIcon: "RP", website: "https://replicate.com", notice: { apiKeyUrl: "https://replicate.com/account/api-tokens" }, serviceKinds: ["image"] },
  "bfl": { id: "bfl", alias: "bfl", name: "Black Forest Labs", icon: "Image", color: "#1E40AF", textIcon: "BF", website: "https://bfl.ai", notice: { apiKeyUrl: "https://bfl.ai/dashboard" }, serviceKinds: ["image"] },
  "comfyui": { id: "comfyui", alias: "cfui", name: "ComfyUI", icon: "Image", color: "#EC4899", textIcon: "CU", website: "https://comfy.org", notice: { text: "Local ComfyUI instance." }, serviceKinds: ["image"] },
  "nanobanana": { id: "nanobanana", alias: "nana", name: "Nanobanana", icon: "Image", color: "#F59E0B", textIcon: "NB", website: "https://nanobanana.com", notice: { apiKeyUrl: "https://nanobanana.com" }, serviceKinds: ["image"] },
  "google-pse": { id: "google-pse", alias: "gpse", name: "Google PSE", icon: "Search", color: "#4285F4", textIcon: "GP", website: "https://programmablesearchengine.google.com", notice: { apiKeyUrl: "https://programmablesearchengine.google.com/controlpanel/create" }, serviceKinds: ["webSearch"] },
  "blackbox": { id: "blackbox", alias: "bb", name: "Blackbox AI", icon: "Bot", color: "#5B5FEF", textIcon: "BB", website: "https://blackbox.ai", notice: { apiKeyUrl: "https://www.blackbox.ai/api-management" }, serviceKinds: ["llm"] },
  "commandcode": { id: "commandcode", alias: "cmc", name: "Command Code", icon: "Bot", color: "#000000", textIcon: "CC", website: "https://commandcode.ai", notice: { apiKeyUrl: "https://commandcode.ai/studio" }, serviceKinds: ["llm"] },
  "jina-reader": { id: "jina-reader", alias: "jinar", name: "Jina Reader", icon: "BookOpen", color: "#000000", textIcon: "JR", website: "https://jina.ai/reader", notice: { apiKeyUrl: "https://jina.ai/?sui=apikey" }, serviceKinds: ["webFetch"] },
  "recraft": { id: "recraft", alias: "recraft", name: "Recraft", icon: "Image", color: "#EC4899", textIcon: "RC", website: "https://recraft.ai", notice: { apiKeyUrl: "https://www.recraft.ai/profile/api" }, serviceKinds: ["image"] },
  "runwayml": { id: "runwayml", alias: "runway", name: "Runway ML", icon: "Video", color: "#000000", textIcon: "RW", website: "https://runwayml.com", notice: { apiKeyUrl: "https://dev.runwayml.com" }, serviceKinds: ["image", "video"] },
  "topaz": { id: "topaz", alias: "topaz", name: "Topaz", icon: "Image", color: "#059669", textIcon: "TP", website: "https://topazlabs.com", notice: { apiKeyUrl: "https://topazlabs.com/account" }, serviceKinds: ["image"] },
};

// ── Web Cookie Providers ───────────────────────────────────────────────────
export const WEB_COOKIE_PROVIDERS = {
  "grok-web": { id: "grok-web", alias: "gw", name: "Grok Web (Subscription)", icon: "Sparkles", color: "#1DA1F2", textIcon: "GW", website: "https://grok.com", authType: "cookie", authHint: "Paste your sso= cookie value from grok.com", passthroughModels: true, serviceKinds: ["llm"] },
  "perplexity-web": { id: "perplexity-web", alias: "pw", name: "Perplexity Web (Pro/Max)", icon: "Search", color: "#20808D", textIcon: "PW", website: "https://www.perplexity.ai", authType: "cookie", authHint: "Paste your __Secure-next-auth.session-token cookie value from perplexity.ai", serviceKinds: ["llm"] },
};

// ── Compatible prefixes ────────────────────────────────────────────────────
export const OPENAI_COMPATIBLE_PREFIX = "openai-compatible-";
export const ANTHROPIC_COMPATIBLE_PREFIX = "anthropic-compatible-";
export const CUSTOM_EMBEDDING_PREFIX = "custom-embedding-";

export function isOpenAICompatibleProvider(providerId) {
  return typeof providerId === "string" && providerId.startsWith(OPENAI_COMPATIBLE_PREFIX);
}

export function isAnthropicCompatibleProvider(providerId) {
  return typeof providerId === "string" && providerId.startsWith(ANTHROPIC_COMPATIBLE_PREFIX);
}

// ── Combined providers (backward compat) ───────────────────────────────────
export const AI_PROVIDERS = { ...FREE_PROVIDERS, ...FREE_TIER_PROVIDERS, ...OAUTH_PROVIDERS, ...APIKEY_PROVIDERS, ...WEB_COOKIE_PROVIDERS };

// Main PROVIDERS object used by pages (backward compatible flat dict)
export const PROVIDERS = AI_PROVIDERS;

// ── Alias/ID helpers ───────────────────────────────────────────────────────
export function getProviderAlias(providerId) {
  const provider = AI_PROVIDERS[providerId];
  return provider?.alias || providerId;
}

export function getProviderByAlias(alias) {
  for (const provider of Object.values(AI_PROVIDERS)) {
    if (provider.alias === alias || provider.id === alias) return provider;
  }
  return null;
}

export function resolveProviderId(aliasOrId) {
  const provider = getProviderByAlias(aliasOrId);
  return provider?.id || aliasOrId;
}

export const ALIAS_TO_ID = Object.values(AI_PROVIDERS).reduce((acc, p) => { acc[p.alias] = p.id; return acc; }, {});
export const ID_TO_ALIAS = Object.values(AI_PROVIDERS).reduce((acc, p) => { acc[p.id] = p.alias; return acc; }, {});

// ── Providers by service kind ──────────────────────────────────────────────
export function getProvidersByKind(kind) {
  return Object.values(AI_PROVIDERS)
    .filter((p) => {
      const kinds = p.serviceKinds ?? ["llm"];
      if (!kinds.includes(kind)) return false;
      if (p.hidden) return false;
      return true;
    })
    .sort((a, b) => (a.mediaPriority ?? 100) - (b.mediaPriority ?? 100));
}

export function getKindConfig(kindId) {
  return MEDIA_PROVIDER_KINDS.find((k) => k.id === kindId);
}

// ── Media provider kinds ───────────────────────────────────────────────────
export const MEDIA_PROVIDER_KINDS = [
  { id: "embedding",   label: "Embedding",      icon: "Binary",           endpoint: { method: "POST", path: "/v1/embeddings" } },
  { id: "tts",         label: "Text To Speech",  icon: "Volume2",          endpoint: { method: "POST", path: "/v1/audio/speech" } },
  { id: "stt",         label: "Speech To Text",  icon: "Mic",              endpoint: { method: "POST", path: "/v1/audio/transcriptions" } },
  { id: "webSearch",   label: "Web Search",      icon: "Search",           endpoint: { method: "POST", path: "/v1/search" } },
  { id: "webFetch",    label: "Web Fetch",       icon: "Globe",            endpoint: { method: "POST", path: "/v1/web/fetch" } },
  { id: "image",       label: "Text to Image",   icon: "Image",            endpoint: { method: "POST", path: "/v1/images/generations" } },
  { id: "imageToText", label: "Image to Text",   icon: "Eye",              endpoint: { method: "POST", path: "/v1/images/understanding" } },
  { id: "video",       label: "Video",           icon: "Video",            endpoint: { method: "POST", path: "/v1/video/generations" } },
  { id: "music",       label: "Music",           icon: "Music",            endpoint: { method: "POST", path: "/v1/audio/music" } },
];

// ── Usage/quota provider filters ───────────────────────────────────────────
// Providers that support usage/quota API (placeholder for future usage UI)
export const USAGE_SUPPORTED_PROVIDERS = [
  "claude", "antigravity", "kiro", "github", "codex",
  "ollama", "gemini-cli", "glm", "glm-cn", "minimax", "minimax-cn", "qoder",
];

// Subset using API key auth (still shown on quota page)
export const USAGE_APIKEY_PROVIDERS = [
  "glm", "glm-cn", "minimax", "minimax-cn",
];

// ── Auth methods ───────────────────────────────────────────────────────────
export const AUTH_METHODS = {
  oauth: { id: "oauth", name: "OAuth", icon: "Lock" },
  apikey: { id: "apikey", name: "API Key", icon: "Key" },
  cookie: { id: "cookie", name: "Browser Cookie", icon: "Cookie" },
};
