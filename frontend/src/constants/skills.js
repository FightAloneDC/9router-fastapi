// Agent Skills metadata — single source of truth for /skills page.
// Each skill = 1 raw GitHub URL the user copies and pastes to any AI agent.

const REPO = 'FightAloneDC/9router-fastapi'
const BRANCH = 'main'
const SKILL_PATH = 'skills'

export const SKILLS_REPO_URL = `https://github.com/${REPO}`
export const SKILLS_BRANCH = BRANCH
export const SKILLS_RAW_BASE = `https://raw.githubusercontent.com/${REPO}/refs/heads/${BRANCH}/${SKILL_PATH}`
export const SKILLS_BLOB_BASE = `https://github.com/${REPO}/blob/${BRANCH}/${SKILL_PATH}`
export const SKILLS_TREE_URL = `${SKILLS_REPO_URL}/tree/${BRANCH}/${SKILL_PATH}`

export const SKILLS = [
  {
    id: '9router',
    name: '9Router (Entry)',
    description: 'Setup + index of all capabilities. Start here — covers base URL, auth, model discovery, and links to every capability skill.',
    endpoint: null,
    icon: 'Hub',
    isEntry: true,
  },
  {
    id: '9router-chat',
    name: 'Chat',
    description: 'Chat / code-gen via OpenAI or Anthropic format with streaming.',
    endpoint: '/v1/chat/completions',
    icon: 'MessageSquare',
  },
  {
    id: '9router-image',
    name: 'Image Generation',
    description: 'Text-to-image via DALL-E, Imagen, FLUX, MiniMax, SDWebUI…',
    endpoint: '/v1/images/generations',
    icon: 'Image',
  },
  {
    id: '9router-tts',
    name: 'Text-to-Speech',
    description: 'OpenAI / ElevenLabs / Edge / Google / Deepgram voices.',
    endpoint: '/v1/audio/speech',
    icon: 'Volume2',
  },
  {
    id: '9router-stt',
    name: 'Speech-to-Text',
    description: 'Transcribe audio via OpenAI Whisper, Groq, Gemini, Deepgram, AssemblyAI…',
    endpoint: '/v1/audio/transcriptions',
    icon: 'Mic',
  },
  {
    id: '9router-embeddings',
    name: 'Embeddings',
    description: 'Vectors for RAG / semantic search via OpenAI, Gemini, Mistral…',
    endpoint: '/v1/embeddings',
    icon: 'Binary',
  },
  {
    id: '9router-rerank',
    name: 'Rerank',
    description: 'Score and reorder documents via Cohere, Jina, Voyage, Alims.',
    endpoint: '/v1/rerank',
    icon: 'ArrowUpDown',
  },
  {
    id: '9router-web-search',
    name: 'Web Search',
    description: 'Tavily / Exa / Brave / Serper / SearXNG / Google PSE / You.com.',
    endpoint: '/v1/search',
    icon: 'Search',
  },
  {
    id: '9router-web-fetch',
    name: 'Web Fetch',
    description: 'URL → markdown / text / HTML via Firecrawl, Jina, Tavily, Exa.',
    endpoint: '/v1/web/fetch',
    icon: 'Globe',
  },
]

export function getSkillRawUrl(id) {
  return `${SKILLS_RAW_BASE}/${id}/SKILL.md`
}

export function getSkillBlobUrl(id) {
  return `${SKILLS_BLOB_BASE}/${id}/SKILL.md`
}
