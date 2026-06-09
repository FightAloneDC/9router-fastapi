# Status Fix Provider — Auth Type: API Key

Provider yang sudah ditest dan confirmed working untuk page setup (add API key, fetch models, proxy routing).

## ✅ Sudah Ditest & Fixed (9 provider)

| Provider | ID | Alias | Catatan |
|----------|----|-------|---------|
| OpenRouter | `openrouter` | `openrouter` | |
| NVIDIA NIM | `nvidia` | `nvidia` | |
| Gemini | `gemini` | `gemini` | |
| Alibaba Intl | `alicode-intl` | `alicode-intl` | Base URL difix: `dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| Cerebras | `cerebras` | `cb` | |
| Groq | `groq` | `gq` | |
| Kilo Gateway | `kilo-gateway` | `kg` | |
| Xiaomi MiMo | `xiaomi-mimo` | `mimo` | |
| OpenCode Go | `opencode-go` | `ocg` | Baru ditambahkan, URL validated |
| AskCodi | `askcodi` | `ac` | Baru ditambahkan, tested & working ✅ |
| Mistral | `mistral` | `mi` | Tested & working ✅ |

## ✅ URL Validated via Curl (25 provider)

Provider yang sudah divalidasi URL-nya (401/200 response = OK):

| Provider | ID | Alias | Notes |
|----------|----|-------|-------|
| GLM Coding | `glm` | `glm` | |
| GLM (China) | `glm-cn` | `glm-cn` | |
| Kimi | `kimi` | `kimi` | |
| Minimax Coding | `minimax` | `minimax` | |
| Minimax (China) | `minimax-cn` | `minimax-cn` | |
| Alibaba (CN) | `alicode` | `alicode` | Base URL sudah benar (sama dengan alicode-intl) |
| Xiaomi MiMo (Token Plan) | `xiaomi-tokenplan` | `xmtp` | Region-specific baseURL implemented |
| Volcengine Ark | `volcengine-ark` | `ark` | |
| OpenAI | `openai` | `openai` | |
| Vercel AI Gateway | `vercel-ai-gateway` | `vag` | |
| DeepSeek | `deepseek` | `ds` | |
| Together | `together` | `tg` | |
| Cohere | `cohere` | `co` | |
| SiliconFlow | `siliconflow` | `sf` | |
| Anthropic | `anthropic` | `an` | |
| Volcengine | `volcengine` | `vk` | |
| Kilo Gateway | `kilo-gateway` | `kg` | Already in tested list |
| Tavily | `tavily` | `tavily` | Web search provider (no chat endpoint) |
| Brave Search | `brave-search` | `brave` | Web search provider |
| Serper | `serper` | `serper` | Web search provider |
| Exa | `exa` | `exa` | Web search + fetch provider |
| Fal.ai | `fal-ai` | `fal` | Image generation provider |
| Stability AI | `stability-ai` | `stability` | Image generation provider |
| Jina AI | `jina-ai` | `jina` | Embedding provider |

## ⚠️ Provider dengan Catatan Khusus

| Provider | ID | Issue | Status |
|----------|----|-------|--------|
| Fireworks | `fireworks` | Chat endpoint 404 saat test dengan dummy key | Perlu test dengan API key valid |
| Perplexity | `perplexity` | Tidak punya `/models` endpoint | By design, tidak bisa fetch models |
| Hugging Face | `huggingface` | Tidak pakai OpenAI-compatible format | Inference API format berbeda per model |
| xAI | `xai` | Return 400 (bukan 401) | Mungkin butuh format request khusus |
| Ollama Local | `ollama-local` | Localhost endpoint | Normal, hanya bisa ditest dari localhost |

## ❌ Belum Diimplementasi

| Provider | ID | Alias | Reason |
|----------|----|-------|--------|
| Azure OpenAI | `azure` | `az` | Tidak ada `/models` endpoint (per-deployment) |
| Amazon Bedrock | `amazon-bedrock` | `bedrock` | AWS-specific auth belum diimplementasi |
| Vertex Partner | `vertex-partner` | `vxp` | GCP service account auth |

## Summary

- **11 provider** — fully tested dengan API key asli
- **24 provider** — URL validated (401/200 = endpoint exists)
- **5 provider** — catatan khusus (perlu test lebih lanjut atau by design)
- **3 provider** — belum diimplementasi (butuh auth khusus)

**Total: 43 provider API Key** (dari 45 di `APIKEY_PROVIDERS`, exclude 3 yang belum diimplementasi)
