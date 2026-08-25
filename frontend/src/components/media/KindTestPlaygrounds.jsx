/**
 * Kind-scoped test playgrounds for media provider detail.
 * Used by ProviderDetailPage when route has :kind.
 */
import { useState, useEffect, useMemo, useRef } from 'react'
import {
  Play, Copy, Check, Volume2, Mic, Upload, FileAudio, ImageIcon,
  Download, Search, Loader2,
} from 'lucide-react'
import Card, { CardContent, CardHeader, CardTitle } from '../ui/Card'
import Button from '../ui/Button'
import { useAuthStore } from '../../stores/authStore'
import { copyToClipboard } from '../../utils/clipboard'

function inferPlaygroundModelType(modelId) {
  const mid = (modelId || '').toLowerCase()
  // rerank before embedding — e.g. gte-rerank-v2
  if (/rerank/.test(mid)) return 'rerank'
  if (/embed|e5-|bge-|gte-|nomic|cohere-embed|voyage-/.test(mid)) {
    return 'embedding'
  }
  if (/tts|speech|audio|voice/.test(mid)) return 'tts'
  if (/whisper|transcri|stt|asr/.test(mid)) return 'stt'
  if (/image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion|midjourney/.test(mid)) {
    return 'image'
  }
  return 'llm'
}

function stripPlaygroundPrefix(id, alias, providerId) {
  let raw = String(id || '')
  for (const head of [alias, providerId]) {
    const p = `${head}/`
    if (head && raw.startsWith(p)) raw = raw.slice(p.length)
  }
  return raw
}

/** Derive select options from parent catalog (same as ChatTestPlayground). */
function useKindModelSelect({
  kind,
  models = [],
  disabledModelIds = [],
  providerId,
  providerAlias,
}) {
  const [selectedModel, setSelectedModel] = useState('')
  const prevAliasRef = useRef(providerAlias)

  const availableModels = useMemo(() => {
    const alias = providerAlias || providerId
    const disabled = new Set(disabledModelIds)
    const seen = new Set()
    const rows = []
    for (const m of models) {
      const stored = typeof m === 'string' ? m : m.id
      if (!stored || disabled.has(stored)) continue
      const typed = (typeof m === 'object' && m.type)
        ? m.type
        : inferPlaygroundModelType(stored)
      if (typed !== kind) continue
      const raw = stripPlaygroundPrefix(stored, alias, providerId)
      const id = `${alias}/${raw}`
      if (seen.has(id)) continue
      seen.add(id)
      rows.push({ id })
    }
    return rows
  }, [models, disabledModelIds, providerAlias, providerId, kind])

  useEffect(() => {
    const ids = availableModels.map((m) => m.id)
    const prevAlias = prevAliasRef.current
    const alias = providerAlias || providerId
    prevAliasRef.current = alias

    setSelectedModel((cur) => {
      let next = cur
      const aliasChanged = Boolean(prevAlias && prevAlias !== alias)
      if (aliasChanged && next) {
        const p = `${prevAlias}/`
        if (next.startsWith(p)) {
          next = `${alias}/${next.slice(p.length)}`
        }
      }
      if (next && ids.includes(next)) return next
      if (ids.length > 0) return ids[0]
      return ''
    })
  }, [availableModels, providerAlias, providerId])

  return { availableModels, selectedModel, setSelectedModel }
}

/* ════════════════════════════════════════════════════════════════
   EmbeddingTestPlayground — real API test for embedding providers
   ════════════════════════════════════════════════════════════════ */
function EmbeddingTestPlayground({
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const token = useAuthStore(s => s.token)
  const { availableModels, selectedModel, setSelectedModel } = useKindModelSelect({
    kind: 'embedding',
    models,
    disabledModelIds,
    providerId,
    providerAlias,
  })
  const [input, setInput] = useState('The quick brown fox jumps over the lazy dog')
  const [dimensions, setDimensions] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [copiedRes, setCopiedRes] = useState(false)

  const buildBody = () => {
    const body = { model: selectedModel, input: input.trim() }
    const dim = Number(dimensions)
    if (dimensions && Number.isFinite(dim) && dim > 0) body.dimensions = dim
    return body
  }

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/embeddings \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'`

  const formatResult = (data) => {
    if (!data) return '{\n  "object": "list",\n  "data": [{\n    "object": "embedding",\n    "index": 0,\n    "embedding": [0.002301, -0.019212, ...]\n  }],\n  "model": "..."\n}'
    const clone = JSON.parse(JSON.stringify(data))
    for (const item of (clone.data || [])) {
      if (Array.isArray(item.embedding) && item.embedding.length > 4) {
        item.embedding = [...item.embedding.slice(0, 4).map(v => parseFloat(v.toFixed(6))), `... (${item.embedding.length} dims)`]
      }
    }
    return JSON.stringify(clone, null, 2)
  }

  const handleRun = async () => {
    if (!selectedModel || !input.trim()) return
    setRunning(true)
    setError('')
    setResult(null)
    setLatency(null)
    const start = Date.now()
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch('/v1/embeddings', { method: 'POST', headers, body: JSON.stringify(buildBody()) })
      const latencyMs = Date.now() - start
      const data = await res.json()
      if (!res.ok) setError(data?.error?.message || data?.error || `HTTP ${res.status}`)
      else { setResult(data); setLatency(latencyMs) }
    } catch (e) { setError(e.message || 'Network error') }
    finally { setRunning(false) }
  }

  const activeConns = connections.filter(c => c.provider === providerId && c.is_active !== false)

  return (
    <Card>
      <CardContent>
        <h2 className="text-lg font-semibold text-zinc-100 mb-4">Test Playground</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Model</label>
            {availableModels.length > 0 ? (
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
              </select>
            ) : (
              <input value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                placeholder={`${providerAlias}/model-name`}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
            )}
            {availableModels.length === 0 && (
              <p className="text-[10px] text-zinc-600 mt-1">
                No enabled embedding models. Type model ID manually.
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Input Text</label>
            <input value={input} onChange={e => setInput(e.target.value)} placeholder="The quick brown fox..."
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Dimensions{' '}
              <span className="text-zinc-600">
                (optional; OpenAI-compat — proxied per provider)
              </span>
            </label>
            <input type="number" min="1" value={dimensions} onChange={e => setDimensions(e.target.value)} placeholder="e.g. 256, 512, 1024, 2048"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Curl</span>
              <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                {copiedCurl ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                {copiedCurl ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-32">{curlSnippet}</pre>
          </div>

          <Button onClick={handleRun} loading={running} disabled={!selectedModel || !input.trim() || activeConns.length === 0} icon={Play} className="w-full">
            {running ? 'Running...' : 'Run'}
          </Button>
          {activeConns.length === 0 && <p className="text-xs text-amber-500 -mt-2">Add and enable a connection first.</p>}

          {error && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3 break-words">{error}</div>}

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Response {latency != null && <span className="font-normal normal-case text-zinc-600">⚡ {latency}ms</span>}
              </span>
              {result && (
                <button onClick={() => { copyToClipboard(formatResult(result)).then(ok => { if (ok) { setCopiedRes(true); setTimeout(() => setCopiedRes(false), 2000) } }) }}
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                  {copiedRes ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                  {copiedRes ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-300 font-mono overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">{formatResult(result)}</pre>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   RerankTestPlayground — real API test for rerank providers
   ════════════════════════════════════════════════════════════════ */
function RerankTestPlayground({
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const token = useAuthStore(s => s.token)
  const { availableModels, selectedModel, setSelectedModel } = useKindModelSelect({
    kind: 'rerank',
    models,
    disabledModelIds,
    providerId,
    providerAlias,
  })
  const [query, setQuery] = useState('What is the capital of France?')
  const [documentsText, setDocumentsText] = useState('Paris is the capital of France.\nBerlin is the capital of Germany.\nThe Eiffel Tower is in Paris.')
  const [topN, setTopN] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [copiedRes, setCopiedRes] = useState(false)

  const documents = documentsText.split('\n').map(d => d.trim()).filter(Boolean)

  const buildBody = () => {
    const body = { model: selectedModel, query: query.trim(), documents }
    const n = Number(topN)
    if (topN && Number.isFinite(n) && n > 0) body.top_n = n
    return body
  }

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/rerank \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'`

  const formatResult = (data) => {
    if (!data) return '{\n  "results": [\n    { "index": 0, "relevance_score": 0.98, "document": "..." }\n  ],\n  "model": "..."\n}'
    return JSON.stringify(data, null, 2)
  }

  const handleRun = async () => {
    if (!selectedModel || !query.trim() || documents.length === 0) return
    setRunning(true)
    setError('')
    setResult(null)
    setLatency(null)
    const start = Date.now()
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch('/v1/rerank', { method: 'POST', headers, body: JSON.stringify(buildBody()) })
      const latencyMs = Date.now() - start
      const data = await res.json()
      if (!res.ok) setError(data?.error?.message || data?.error || `HTTP ${res.status}`)
      else { setResult(data); setLatency(latencyMs) }
    } catch (e) { setError(e.message || 'Network error') }
    finally { setRunning(false) }
  }

  const activeConns = connections.filter(c => c.provider === providerId && c.is_active !== false)

  return (
    <Card>
      <CardContent>
        <h2 className="text-lg font-semibold text-zinc-100 mb-4">Test Playground</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Model</label>
            {availableModels.length > 0 ? (
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
              </select>
            ) : (
              <input value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                placeholder={`${providerAlias}/model-name`}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
            )}
            {availableModels.length === 0 && (
              <p className="text-[10px] text-zinc-600 mt-1">
                No enabled rerank models. Type model ID manually.
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Query</label>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="What is the capital of France?"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Documents <span className="text-zinc-600">(one per line)</span></label>
            <textarea value={documentsText} onChange={e => setDocumentsText(e.target.value)} rows={4}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500 resize-y" />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Top N <span className="text-zinc-600">(optional)</span></label>
            <input type="number" min="1" value={topN} onChange={e => setTopN(e.target.value)} placeholder="e.g. 3"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Curl</span>
              <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                {copiedCurl ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                {copiedCurl ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-32">{curlSnippet}</pre>
          </div>

          <Button onClick={handleRun} loading={running} disabled={!selectedModel || !query.trim() || documents.length === 0 || activeConns.length === 0} icon={Play} className="w-full">
            {running ? 'Running...' : 'Run'}
          </Button>
          {activeConns.length === 0 && <p className="text-xs text-amber-500 -mt-2">Add and enable a connection first.</p>}

          {error && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3 break-words">{error}</div>}

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Response {latency != null && <span className="font-normal normal-case text-zinc-600">⚡ {latency}ms</span>}
              </span>
              {result && (
                <button onClick={() => { copyToClipboard(formatResult(result)).then(ok => { if (ok) { setCopiedRes(true); setTimeout(() => setCopiedRes(false), 2000) } }) }}
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                  {copiedRes ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                  {copiedRes ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-300 font-mono overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">{formatResult(result)}</pre>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   TtsTestPlayground — Voice synthesis playground for /v1/audio/speech
   ════════════════════════════════════════════════════════════════ */
function TtsTestPlayground({
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const token = useAuthStore(s => s.token)
  const { availableModels, selectedModel, setSelectedModel } = useKindModelSelect({
    kind: 'tts',
    models,
    disabledModelIds,
    providerId,
    providerAlias,
  })
  const [voice, setVoice] = useState('')
  const [input, setInput] = useState('Hello, this is a text to speech test.')
  const [responseFormat, setResponseFormat] = useState('mp3') // mp3 | json
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [jsonResponse, setJsonResponse] = useState(null)
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [availableVoices, setAvailableVoices] = useState([])
  const [loadingVoices, setLoadingVoices] = useState(false)
  const audioUrlRef = useRef('')

  // Fetch available voices for this provider
  useEffect(() => {
    if (!providerId) return
    setLoadingVoices(true)
    fetch(`/v1/audio/voices?provider=${providerId}`, {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(data => {
        const voices = data.voices || data.data || []
        setAvailableVoices(Array.isArray(voices) ? voices : [])
      })
      .catch(() => setAvailableVoices([]))
      .finally(() => setLoadingVoices(false))
  }, [providerId, token])

  // Cleanup object URL on unmount or when audioUrl changes
  useEffect(() => {
    return () => { if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current) }
  }, [])

  const buildBody = () => {
    const body = { model: selectedModel, input: input.trim() }
    if (voice.trim()) body.voice = voice.trim()
    return body
  }

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/audio/speech${responseFormat === 'json' ? '?response_format=json' : ''} \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer *** || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'${responseFormat === 'json' ? '' : ' \\\n  --output speech.mp3'}`

  const handleRun = async () => {
    if (!selectedModel || !input.trim()) return
    setRunning(true)
    setError('')
    setJsonResponse(null)
    if (audioUrlRef.current) { URL.revokeObjectURL(audioUrlRef.current); audioUrlRef.current = '' }
    setAudioUrl('')
    setLatency(null)
    const start = Date.now()
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`
      const url = `/v1/audio/speech${responseFormat === 'json' ? '?response_format=json' : ''}`
      const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(buildBody()) })
      const latencyMs = Date.now() - start
      setLatency(latencyMs)
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        setError(d?.error?.message || d?.error || `HTTP ${res.status}`)
        return
      }
      if (responseFormat === 'json') {
        const data = await res.json()
        setJsonResponse(data)
        if (data.audio) {
          const audioBlob = await fetch(`data:audio/mp3;base64,${data.audio}`).then(r => r.blob())
          const objUrl = URL.createObjectURL(audioBlob)
          audioUrlRef.current = objUrl
          setAudioUrl(objUrl)
        }
      } else {
        const blob = await res.blob()
        const objUrl = URL.createObjectURL(blob)
        audioUrlRef.current = objUrl
        setAudioUrl(objUrl)
      }
    } catch (e) {
      setError(e.message || 'Network error')
    } finally {
      setRunning(false)
    }
  }

  const activeConns = connections.filter(c => c.provider === providerId && c.is_active !== false)

  return (
    <Card>
      <CardContent>
        <h2 className="text-lg font-semibold text-zinc-100 mb-4 flex items-center gap-2">
          <Volume2 size={18} className="text-purple-400" />
          Test Playground
        </h2>
        <div className="flex flex-col gap-3">
          {/* Model selector */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Model</label>
            {availableModels.length > 0 ? (
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
              </select>
            ) : (
              <input value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                placeholder={`${providerAlias}/tts-model-name`}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
            )}
            {availableModels.length === 0 && (
              <p className="text-[10px] text-zinc-600 mt-1">
                No enabled TTS models. Type model ID manually
                (e.g. {providerAlias}/voice-name).
              </p>
            )}
          </div>

          {/* Voice ID (optional) */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">
              Voice ID <span className="text-zinc-600">(optional — provider default used if empty)</span>
            </label>
            {availableVoices.length > 0 ? (
              <div className="flex gap-2">
                <select value={voice} onChange={e => setVoice(e.target.value)}
                  className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                  <option value="">Default</option>
                  {availableVoices.map((v, i) => {
                    const voiceId = typeof v === 'string' ? v : v.id || v.voice_id || v.name || ''
                    const voiceName = typeof v === 'string' ? v : v.name || v.label || v.id || v.voice_id || ''
                    return <option key={i} value={voiceId}>{voiceName}</option>
                  })}
                </select>
                <input value={voice} onChange={e => setVoice(e.target.value)} placeholder="Custom voice ID"
                  className="w-40 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
              </div>
            ) : (
              <div>
                <input value={voice} onChange={e => setVoice(e.target.value)} placeholder="e.g. alloy, nova, en-US-AriaNeural"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
                {loadingVoices && <p className="text-[10px] text-zinc-600 mt-1">Loading voices...</p>}
              </div>
            )}
          </div>

          {/* Input text */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Input Text</label>
            <textarea value={input} onChange={e => setInput(e.target.value)} placeholder="Hello, this is a text to speech test." rows={3}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500 resize-y" />
          </div>

          {/* Output format */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Output Format</label>
            <select value={responseFormat} onChange={e => setResponseFormat(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
              <option value="mp3">MP3 (Binary)</option>
              <option value="json">JSON (Base64)</option>
            </select>
          </div>

          {/* Curl */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Curl</span>
              <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                {copiedCurl ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                {copiedCurl ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-40">{curlSnippet}</pre>
          </div>

          <Button onClick={handleRun} loading={running} disabled={!selectedModel || !input.trim() || activeConns.length === 0} icon={Play} className="w-full">
            {running ? 'Generating...' : 'Run'}
          </Button>
          {activeConns.length === 0 && <p className="text-xs text-amber-500 -mt-2">Add and enable a connection first.</p>}

          {error && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3 break-words">{error}</div>}

          {/* Response: audio player + optional JSON preview */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Response {latency != null && <span className="font-normal normal-case text-zinc-600">⚡ {latency}ms</span>}
              </span>
              {audioUrl && (
                <a href={audioUrl} download="speech.mp3" className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                  <Download size={12} />
                  Download
                </a>
              )}
            </div>
            {audioUrl ? (
              <audio controls src={audioUrl} className="w-full" />
            ) : (
              <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-500 font-mono overflow-x-auto whitespace-pre-wrap break-all opacity-50">{`// Audio will appear here after running.\n// MP3 mode → binary stream rendered in the player above.\n// JSON mode → { "format": "mp3", "audio": "<base64>" }`}</pre>
            )}

            {jsonResponse && (
              <div className="mt-3">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">JSON Response</span>
                <pre className="mt-1.5 bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-300 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-40">
{JSON.stringify({
  format: jsonResponse.format,
  audio: jsonResponse.audio ? `${String(jsonResponse.audio).substring(0, 100)}... (${String(jsonResponse.audio).length} chars)` : ''
}, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   SttTestPlayground — Speech-to-text playground for /v1/audio/transcriptions
   ════════════════════════════════════════════════════════════════ */
function SttTestPlayground({
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const token = useAuthStore(s => s.token)
  const { availableModels, selectedModel, setSelectedModel } = useKindModelSelect({
    kind: 'stt',
    models,
    disabledModelIds,
    providerId,
    providerAlias,
  })
  const [file, setFile] = useState(null)
  const [language, setLanguage] = useState('')
  const [prompt, setPrompt] = useState('')
  const [responseFormat, setResponseFormat] = useState('json')
  const [temperature, setTemperature] = useState('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [resultText, setResultText] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [copiedRes, setCopiedRes] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B'
    const k = 1024, sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`
  }

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    setError('')
  }

  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation()
    setDragActive(false)
    const f = e.dataTransfer?.files?.[0]
    if (f) handleFile(f)
  }

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlSnippet = (() => {
    const parts = [
      `curl -X POST ${endpoint}/v1/audio/transcriptions \\`,
      `  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\`,
      `  -F "file=@${file?.name || 'audio.mp3'}" \\`,
      `  -F "model=${selectedModel || `${providerAlias}/model-name`}"`,
    ]
    if (language.trim()) parts.push(`  \\\n  -F "language=${language.trim()}"`)
    if (prompt.trim()) parts.push(`  \\\n  -F "prompt=${prompt.trim().replace(/"/g, '\\"')}"`)
    if (responseFormat && responseFormat !== 'json') parts.push(`  \\\n  -F "response_format=${responseFormat}"`)
    if (temperature.trim()) parts.push(`  \\\n  -F "temperature=${temperature.trim()}"`)
    return parts.join('\n').replace(/\n {2}\\\n/g, ' \\\n  ')
  })()

  const handleRun = async () => {
    if (!selectedModel || !file) return
    setRunning(true)
    setError('')
    setResult(null)
    setResultText('')
    setLatency(null)
    const start = Date.now()
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('model', selectedModel)
      if (language.trim()) fd.append('language', language.trim())
      if (prompt.trim()) fd.append('prompt', prompt.trim())
      if (responseFormat) fd.append('response_format', responseFormat)
      if (temperature.trim()) fd.append('temperature', temperature.trim())

      const headers = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch('/v1/audio/transcriptions', { method: 'POST', headers, body: fd })
      const latencyMs = Date.now() - start
      setLatency(latencyMs)

      const ct = res.headers.get('content-type') || ''
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          if (ct.includes('application/json')) {
            const d = await res.json()
            msg = d?.error?.message || d?.detail || d?.error || msg
          } else {
            const t = await res.text()
            if (t) msg = t
          }
        } catch {}
        setError(msg)
        return
      }

      if (ct.includes('application/json')) {
        const data = await res.json()
        setResult(data)
        setResultText(data?.text || '')
      } else {
        const text = await res.text()
        setResultText(text)
        setResult({ text })
      }
    } catch (e) {
      setError(e.message || 'Network error')
    } finally {
      setRunning(false)
    }
  }

  const activeConns = connections.filter(c => c.provider === providerId && c.is_active !== false)

  return (
    <Card>
      <CardContent>
        <h2 className="text-lg font-semibold text-zinc-100 mb-4 flex items-center gap-2">
          <Mic size={18} className="text-orange-400" />
          Test Playground
        </h2>
        <div className="flex flex-col gap-3">
          {/* Model selector */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Model</label>
            {availableModels.length > 0 ? (
              <select value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                {availableModels.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
              </select>
            ) : (
              <input value={selectedModel} onChange={e => setSelectedModel(e.target.value)}
                placeholder={`${providerAlias}/whisper-1`}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
            )}
            {availableModels.length === 0 && (
              <p className="text-[10px] text-zinc-600 mt-1">
                No enabled STT models. Type model ID manually
                (e.g. {providerAlias}/whisper-1).
              </p>
            )}
          </div>

          {/* Audio file dropzone */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Audio File</label>
            <div
              onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true) }}
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(true) }}
              onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setDragActive(false) }}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex items-center gap-3 border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors ${dragActive ? 'border-orange-500 bg-orange-500/5' : 'border-zinc-700 bg-zinc-900 hover:border-zinc-600'}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,.mp3,.wav,.m4a,.webm,.ogg,.flac,.opus"
                onChange={(e) => handleFile(e.target.files?.[0])}
                className="hidden"
              />
              {file ? (
                <>
                  <FileAudio size={20} className="text-orange-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-zinc-200 truncate">{file.name}</div>
                    <div className="text-[10px] text-zinc-500">{formatBytes(file.size)} · {file.type || 'audio/*'}</div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); setFile(null); if (fileInputRef.current) fileInputRef.current.value = '' }}
                    className="text-zinc-500 hover:text-zinc-300"
                    aria-label="Remove file"
                  >
                    <X size={16} />
                  </button>
                </>
              ) : (
                <>
                  <Upload size={20} className="text-zinc-500 shrink-0" />
                  <div className="flex-1">
                    <div className="text-sm text-zinc-300">Click to upload or drop an audio file</div>
                    <div className="text-[10px] text-zinc-600">mp3, wav, m4a, webm, ogg, flac, opus</div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Language + Response format (two columns) */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Language <span className="text-zinc-600">(optional)</span></label>
              <input value={language} onChange={e => setLanguage(e.target.value)} placeholder="e.g. en, id, ja"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 font-mono focus:outline-none focus:border-primary-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Response Format</label>
              <select value={responseFormat} onChange={e => setResponseFormat(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500">
                <option value="json">json</option>
                <option value="text">text</option>
                <option value="verbose_json">verbose_json</option>
                <option value="srt">srt</option>
                <option value="vtt">vtt</option>
              </select>
            </div>
          </div>

          {/* Prompt */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Prompt <span className="text-zinc-600">(optional context hint)</span></label>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="e.g. proper nouns, glossary terms…" rows={2}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500 resize-y" />
          </div>

          {/* Temperature */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Temperature <span className="text-zinc-600">(optional, 0.0 – 1.0)</span></label>
            <input type="number" min="0" max="1" step="0.1" value={temperature} onChange={e => setTemperature(e.target.value)} placeholder="e.g. 0.0"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          {/* Curl */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Curl</span>
              <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                {copiedCurl ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                {copiedCurl ? 'Copied' : 'Copy'}
              </button>
            </div>
            <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-400 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-40">{curlSnippet}</pre>
          </div>

          <Button onClick={handleRun} loading={running} disabled={!selectedModel || !file || activeConns.length === 0} icon={Play} className="w-full">
            {running ? 'Transcribing...' : 'Transcribe'}
          </Button>
          {activeConns.length === 0 && <p className="text-xs text-amber-500 -mt-2">Add and enable a connection first.</p>}

          {error && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg p-3 break-words">{error}</div>}

          {/* Response: transcript text + raw payload */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">
                Transcript {latency != null && <span className="font-normal normal-case text-zinc-600">⚡ {latency}ms</span>}
              </span>
              {resultText && (
                <button onClick={() => { copyToClipboard(resultText).then(ok => { if (ok) { setCopiedRes(true); setTimeout(() => setCopiedRes(false), 2000) } }) }}
                  className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300">
                  {copiedRes ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                  {copiedRes ? 'Copied' : 'Copy'}
                </button>
              )}
            </div>
            {resultText ? (
              <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-100 font-sans overflow-x-auto whitespace-pre-wrap break-words max-h-60">{resultText}</pre>
            ) : (
              <pre className="bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-500 font-mono overflow-x-auto whitespace-pre-wrap break-all opacity-50">{`// Transcript will appear here after running.\n// json mode → { "text": "..." }\n// verbose_json → adds segments, language, duration\n// srt / vtt → subtitle text\n// text → plain text body`}</pre>
            )}

            {result && typeof result === 'object' && (Object.keys(result).length > 1 || result.text) && (
              <div className="mt-3">
                <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Raw Response</span>
                <pre className="mt-1.5 bg-zinc-900 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-300 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-60">{JSON.stringify(result, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   SearchTestPlayground — real API test for web search providers
   ════════════════════════════════════════════════════════════════ */
function SearchTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [query, setQuery] = useState('latest AI news')
  const [maxResults, setMaxResults] = useState(5)
  const [searchType, setSearchType] = useState('web')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [copiedRes, setCopiedRes] = useState(false)

  const buildBody = () => ({
    model: providerId,
    query: query.trim(),
    max_results: maxResults,
    search_type: searchType,
  })

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/search \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'`

  const handleRun = async () => {
    if (!query.trim()) return
    setRunning(true); setError(''); setResult(null); setLatency(null)
    const start = Date.now()
    try {
      const res = await fetch('/v1/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token || ''}` },
        body: JSON.stringify(buildBody()),
      })
      const data = await res.json()
      setLatency(Date.now() - start)
      if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
      setResult(data)
    } catch (e) { setError(e.message); setLatency(Date.now() - start) } finally { setRunning(false) }
  }

  return (
    <Card className="bg-zinc-900/50 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Search size={16} className="text-primary-400" />
          Search Test Playground
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Search Type</label>
            <select value={searchType} onChange={(e) => setSearchType(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200">
              <option value="web">Web</option>
              <option value="news">News</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Max Results</label>
            <input type="number" value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value) || 5)}
              min={1} max={50}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" />
          </div>
        </div>
        <div>
          <label className="text-xs text-zinc-400 mb-1 block">Query</label>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Enter search query..."
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200"
            onKeyDown={(e) => e.key === 'Enter' && handleRun()} />
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleRun} disabled={running || !query.trim()}>
            {running ? <Loader2 size={14} className="animate-spin mr-1" /> : <Play size={14} className="mr-1" />}
            Search
          </Button>
          {latency && <span className="text-xs text-zinc-500 self-center">{latency}ms</span>}
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-zinc-400">cURL</label>
            <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
              className="text-xs text-zinc-500 hover:text-primary-400 cursor-pointer">{copiedCurl ? 'Copied!' : 'Copy'}</button>
          </div>
          <pre className="bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap break-all">{curlSnippet}</pre>
        </div>
        {error && <div className="text-xs text-red-400 bg-red-500/10 rounded-lg p-3">{error}</div>}
        {result && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-zinc-400">Results ({(result.results || []).length})</label>
              <button onClick={() => { copyToClipboard(JSON.stringify(result, null, 2)).then(ok => { if (ok) { setCopiedRes(true); setTimeout(() => setCopiedRes(false), 2000) } }) }}
                className="text-xs text-zinc-500 hover:text-primary-400 cursor-pointer">{copiedRes ? 'Copied!' : 'Copy JSON'}</button>
            </div>
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {(result.results || []).map((r, i) => (
                <div key={i} className="bg-zinc-800/80 rounded-lg p-3 border border-zinc-700/50">
                  <div className="flex items-start gap-2">
                    <span className="text-[10px] text-zinc-500 font-mono mt-0.5 shrink-0">#{r.position || i + 1}</span>
                    <div className="flex-1 min-w-0">
                      <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary-400 hover:underline truncate block">
                        {r.title || r.url}
                      </a>
                      {r.display_url && <p className="text-[10px] text-zinc-500 mt-0.5">{r.display_url}</p>}
                      {r.snippet && <p className="text-xs text-zinc-400 mt-1 line-clamp-2">{r.snippet}</p>}
                    </div>
                    {r.score != null && <span className="text-[10px] text-zinc-500 shrink-0">{(r.score * 100).toFixed(0)}%</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   ImageTestPlayground — real API test for image generation providers
   ════════════════════════════════════════════════════════════════ */
function ImageTestPlayground({
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const token = useAuthStore(s => s.token)
  const { availableModels, selectedModel, setSelectedModel } = useKindModelSelect({
    kind: 'image',
    models,
    disabledModelIds,
    providerId,
    providerAlias,
  })
  const [prompt, setPrompt] = useState('A beautiful sunset over the ocean, digital art')
  const [size, setSize] = useState('1024x1024')
  const [n, setN] = useState(1)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)

  const buildBody = () => ({
    model: selectedModel || `${providerId}/default`,
    prompt: prompt.trim(),
    size,
    n,
  })

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/images/generations \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'`

  const handleRun = async () => {
    if (!prompt.trim()) return
    setRunning(true); setError(''); setResult(null); setLatency(null)
    const start = Date.now()
    try {
      const res = await fetch('/v1/images/generations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token || ''}` },
        body: JSON.stringify(buildBody()),
      })
      const data = await res.json()
      setLatency(Date.now() - start)
      if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
      setResult(data)
    } catch (e) { setError(e.message); setLatency(Date.now() - start) } finally { setRunning(false) }
  }

  return (
    <Card className="bg-zinc-900/50 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <ImageIcon size={16} className="text-primary-400" />
          Image Generation Test Playground
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-xs text-zinc-400 mb-1 block">Model</label>
          {availableModels.length > 0 ? (
            <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200">
              {availableModels.map(m => <option key={m.id} value={m.id}>{m.id}</option>)}
            </select>
          ) : (
            <input value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}
              placeholder={`${providerId}/model-name`}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" />
          )}
        </div>
        <div>
          <label className="text-xs text-zinc-400 mb-1 block">Prompt</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} placeholder="Describe the image..."
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 resize-none" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Size</label>
            <select value={size} onChange={(e) => setSize(e.target.value)}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200">
              <option value="256x256">256x256</option>
              <option value="512x512">512x512</option>
              <option value="1024x1024">1024x1024</option>
              <option value="1792x1024">1792x1024</option>
              <option value="1024x1792">1024x1792</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Count (n)</label>
            <input type="number" value={n} onChange={(e) => setN(Number(e.target.value) || 1)} min={1} max={4}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" />
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={handleRun} disabled={running || !prompt.trim()}>
            {running ? <Loader2 size={14} className="animate-spin mr-1" /> : <Play size={14} className="mr-1" />}
            Generate
          </Button>
          {latency && <span className="text-xs text-zinc-500 self-center">{latency}ms</span>}
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-zinc-400">cURL</label>
            <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
              className="text-xs text-zinc-500 hover:text-primary-400 cursor-pointer">{copiedCurl ? 'Copied!' : 'Copy'}</button>
          </div>
          <pre className="bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap break-all">{curlSnippet}</pre>
        </div>
        {error && <div className="text-xs text-red-400 bg-red-500/10 rounded-lg p-3">{error}</div>}
        {result && (
          <div>
            <label className="text-xs text-zinc-400 mb-2 block">Generated Images</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(result.data || []).map((img, i) => (
                <div key={i} className="bg-zinc-800/80 rounded-lg p-2 border border-zinc-700/50">
                  {img.b64_json ? (
                    <img src={`data:image/png;base64,${img.b64_json}`} alt={`Generated ${i + 1}`}
                      className="w-full rounded" />
                  ) : img.url ? (
                    <img src={img.url} alt={`Generated ${i + 1}`} className="w-full rounded"
                      onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'block' }} />
                  ) : null}
                  {img.url && <p className="text-[10px] text-zinc-500 mt-1 truncate">{img.url}</p>}
                  {img.revised_prompt && <p className="text-[10px] text-zinc-400 mt-1 italic">{img.revised_prompt}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}


export default function KindTestPlayground({
  kind,
  providerId,
  providerAlias,
  connections,
  models = [],
  disabledModelIds = [],
}) {
  const props = {
    providerId,
    providerAlias,
    connections,
    models,
    disabledModelIds,
  }
  if (kind === 'tts') return <TtsTestPlayground {...props} />
  if (kind === 'stt') return <SttTestPlayground {...props} />
  if (kind === 'webSearch') return <SearchTestPlayground {...props} />
  if (kind === 'image') return <ImageTestPlayground {...props} />
  if (kind === 'embedding') {
    return <EmbeddingTestPlayground {...props} />
  }
  if (kind === 'rerank') return <RerankTestPlayground {...props} />
  return (
    <Card className="bg-zinc-900/50 border-zinc-800">
      <CardContent className="py-8 text-center text-sm text-zinc-500">
        Playground not available for this kind
      </CardContent>
    </Card>
  )
}
