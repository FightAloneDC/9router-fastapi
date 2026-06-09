import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Trash2, Key, Eye, EyeOff,
  ChevronUp, ChevronDown, CheckCircle2, AlertCircle,
  Loader2, Wifi, Edit2, ExternalLink, X, Copy, Check,
  Beaker, Download, Network, Ban, RotateCcw, Search, Play, MessageSquare,
  Cookie, Lock, TriangleAlert, Info, Plug,
} from 'lucide-react'
import Card, { CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { useNotificationStore } from '../stores/notificationStore'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import { providersApi } from '../api/providers'
import { proxyPoolsApi } from '../api/proxyPools'
import { settingsApi } from '../api/settings'
import useCatalogStore from '../stores/catalogStore'
import { copyToClipboard } from '../utils/clipboard'
import CompatibleModelsSection from '../components/CompatibleModelsSection'
import { fetchSuggestedModels } from '../utils/providerModelsFetcher'
import EditCompatibleNodeModal from '../components/EditCompatibleNodeModal'
import OAuthModal from '../components/OAuthModal'
import OAuthEditModal from '../components/OAuthEditModal'
import KiroAuthModal from '../components/KiroAuthModal'
import CursorAuthModal from '../components/CursorAuthModal'
import GitLabAuthModal from '../components/GitLabAuthModal'
import { useAuthStore } from '../stores/authStore'

const COMPATIBLE_TYPES = new Set(['openai-compatible', 'anthropic-compatible'])

// Per-connection OAuth detection (for providers that support both OAuth and PAT like qoder)
function isConnectionOAuth(conn, providerId) {
  const catalog = useCatalogStore.getState().providers
  const p = catalog[providerId]
  // OAuth-style editing: OAuth providers, free providers, or providers that support PAT
  if (p?.authType === 'oauth' || p?.authType === 'free' || p?.supportsPAT) return true
  return false
}

const TYPE_BADGE_STYLES = {
  llm: 'bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25',
  embedding: 'bg-blue-500/15 text-blue-400 hover:bg-blue-500/25',
  tts: 'bg-purple-500/15 text-purple-400 hover:bg-purple-500/25',
  stt: 'bg-orange-500/15 text-orange-400 hover:bg-orange-500/25',
  image: 'bg-pink-500/15 text-pink-400 hover:bg-pink-500/25',
  webSearch: 'bg-cyan-500/15 text-cyan-400 hover:bg-cyan-500/25',
  webFetch: 'bg-teal-500/15 text-teal-400 hover:bg-teal-500/25',
  imageToText: 'bg-rose-500/15 text-rose-400 hover:bg-rose-500/25',
  video: 'bg-amber-500/15 text-amber-400 hover:bg-amber-500/25',
  music: 'bg-indigo-500/15 text-indigo-400 hover:bg-indigo-500/25',
}

function inferModelType(modelId) {
  const mid = (modelId || '').toLowerCase()
  if (/embed|e5-|bge-|gte-|nomic|cohere-embed|voyage-/.test(mid)) return 'embedding'
  if (/tts|speech|audio|voice/.test(mid)) return 'tts'
  if (/whisper|transcri|stt|asr/.test(mid)) return 'stt'
  if (/image|imagen|dall-?e|flux|sdxl|sd-|stable-diffusion|midjourney/.test(mid)) return 'image'
  return 'llm'
}


/* ════════════════════════════════════════════════════════════════
   CooldownTimer — countdown timer for connection cooldowns
   ════════════════════════════════════════════════════════════════ */
function CooldownTimer({ until }) {
  const [remaining, setRemaining] = useState('')

  useEffect(() => {
    const update = () => {
      const diff = new Date(until).getTime() - Date.now()
      if (diff <= 0) { setRemaining(''); return }
      const s = Math.floor(diff / 1000)
      if (s < 60) setRemaining(`${s}s`)
      else if (s < 3600) setRemaining(`${Math.floor(s / 60)}m ${s % 60}s`)
      else setRemaining(`${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`)
    }
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [until])

  if (!remaining) return null
  return <span className="text-xs text-orange-500 font-mono">⏱ {remaining}</span>
}


/* ════════════════════════════════════════════════════════════════
   ConfirmModal — lightweight confirmation dialog
   ════════════════════════════════════════════════════════════════ */
function ConfirmModal({ isOpen, onClose, onConfirm, title, message, variant = 'danger' }) {
  if (!isOpen) return null
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title || 'Confirm'}>
      <p className="text-sm text-zinc-300 mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant={variant === 'danger' ? 'danger' : 'primary'} onClick={onConfirm}>
          Confirm
        </Button>
      </div>
    </Modal>
  )
}


/* ════════════════════════════════════════════════════════════════
   ConnectionRow — single connection row with proxy, cooldown, etc.
   ════════════════════════════════════════════════════════════════ */
function ConnectionRow({ connection, proxyPools, isFirst, isLast, onMoveUp, onMoveDown, onToggleActive, onUpdateProxy, onEdit, onDelete, onTest, testing, testResult, isOAuth = false }) {
  const [showProxyDropdown, setShowProxyDropdown] = useState(false)
  const [updatingProxy, setUpdatingProxy] = useState(false)
  const proxyDropdownRef = useRef(null)

  const isActive = connection.is_active ?? true
  const status = connection.test_status || 'untested'

  // OAuth display name logic
  const isEmail = (v) => typeof v === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
  const providerSpecific = connection.providerSpecificData || connection.provider_specific || {}
  const _psd = connection.providerSpecificData || connection.provider_specific || {}
  const _isOAuth = _psd.loginMethod === 'pat' ? false : (connection.auth_type ? connection.auth_type === 'oauth' : isOAuth)
  const displayName = _isOAuth
    ? (isEmail(connection.email) ? connection.email
      : (isEmail(connection.name) ? connection.name
      : (connection.name || connection.email || connection.displayName || "OAuth Account")))
    : (connection.name || 'Unnamed Connection')

  // Cooldown detection from provider_specific fields
  const modelLockUntil = Object.entries(providerSpecific)
    .filter(([k]) => k.startsWith('modelLock_'))
    .map(([, v]) => v).filter(Boolean).sort()[0] || null
  const isCooldown = modelLockUntil && new Date(modelLockUntil).getTime() > Date.now()

  // Token expiry detection for OAuth
  const expiresAt = providerSpecific.expiresAt
  const isTokenExpired = _isOAuth && expiresAt && new Date(expiresAt).getTime() < Date.now()
  const hasRefreshError = _isOAuth && providerSpecific.lastError

  // Proxy info
  const boundProxyPoolId = connection.proxy_pool_id || null
  const proxyPoolMap = new Map((proxyPools || []).map((p) => [p.id, p]))
  const boundProxyPool = boundProxyPoolId ? proxyPoolMap.get(boundProxyPoolId) : null
  const hasAnyProxy = !!boundProxyPoolId

  const proxyDisplayText = boundProxyPool
    ? `Pool: ${boundProxyPool.name}`
    : boundProxyPoolId ? `Pool: ${boundProxyPoolId} (missing)` : ''

  const effectiveStatus = isCooldown && isActive ? 'active' : status

  const getStatusVariant = () => {
    if (!isActive) return 'default'
    if (effectiveStatus === 'connected' || effectiveStatus === 'active' || effectiveStatus === 'success') return 'success'
    if (effectiveStatus === 'error' || effectiveStatus === 'expired' || effectiveStatus === 'unavailable') return 'danger'
    if (effectiveStatus === 'untested') return 'warning'
    return 'default'
  }

  // Close proxy dropdown on outside click
  useEffect(() => {
    if (!showProxyDropdown) return
    const handler = (e) => {
      if (proxyDropdownRef.current && !proxyDropdownRef.current.contains(e.target))
        setShowProxyDropdown(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showProxyDropdown])

  const handleSelectProxy = async (poolId) => {
    setUpdatingProxy(true)
    try { await onUpdateProxy(poolId === '__none__' ? null : poolId) }
    finally { setUpdatingProxy(false); setShowProxyDropdown(false) }
  }

  return (
    <div className={`group flex flex-col gap-3 p-2 rounded-lg sm:flex-row sm:items-center sm:justify-between hover:bg-zinc-800/40 transition-colors ${!isActive ? 'opacity-60' : ''}`}>
      {/* Left side */}
      <div className="flex w-full min-w-0 flex-1 items-start gap-3 sm:items-center">
        {/* Priority arrows */}
        <div className="flex shrink-0 flex-col">
          <button onClick={onMoveUp} disabled={isFirst} className={`p-0.5 rounded ${isFirst ? 'text-zinc-700 cursor-not-allowed' : 'text-zinc-500 hover:text-primary-400 hover:bg-zinc-800'}`}>
            <ChevronUp size={14} />
          </button>
          <button onClick={onMoveDown} disabled={isLast} className={`p-0.5 rounded ${isLast ? 'text-zinc-700 cursor-not-allowed' : 'text-zinc-500 hover:text-primary-400 hover:bg-zinc-800'}`}>
            <ChevronDown size={14} />
          </button>
        </div>

        {_isOAuth ? <Lock size={16} className="shrink-0 text-zinc-500" /> : <Key size={16} className="shrink-0 text-zinc-500" />}

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-zinc-200 truncate">
            {displayName}
          </p>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5">
            <Badge variant={getStatusVariant()} size="sm" dot>
              {!isActive ? 'disabled' : (effectiveStatus || 'untested')}
            </Badge>
            {hasAnyProxy && <Badge variant="info" size="sm">Proxy</Badge>}
            {isTokenExpired && <Badge variant="danger" size="sm">Token Expired</Badge>}
            {hasRefreshError && <Badge variant="warning" size="sm">Refresh Error</Badge>}
            {isCooldown && isActive && <CooldownTimer until={modelLockUntil} />}
            {connection.priority != null && (
              <span className="text-xs text-zinc-500">#{connection.priority}</span>
            )}
          </div>
          {hasAnyProxy && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-zinc-500 truncate max-w-[420px]" title={proxyDisplayText}>{proxyDisplayText}</span>
            </div>
          )}
        </div>
      </div>

      {/* Right side */}
      <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:justify-end">
        <div className="flex flex-wrap gap-1">
          {/* Proxy selector */}
          {(proxyPools || []).length > 0 && (
            <div className="relative" ref={proxyDropdownRef}>
              <button
                onClick={() => setShowProxyDropdown((v) => !v)}
                className={`flex flex-col items-center px-2 py-1 rounded hover:bg-zinc-800 transition-colors ${hasAnyProxy ? 'text-primary-400' : 'text-zinc-500 hover:text-primary-400'}`}
                disabled={updatingProxy}
              >
                <Network size={16} />
                <span className="text-[10px] leading-tight">Proxy</span>
              </button>
              {showProxyDropdown && (
                <div className="absolute right-0 top-full mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg py-1 min-w-[160px]">
                  <button onClick={() => handleSelectProxy('__none__')} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-zinc-700 ${!boundProxyPoolId ? 'text-primary-400 font-medium' : 'text-zinc-300'}`}>None</button>
                  {(proxyPools || []).map((pool) => (
                    <button key={pool.id} onClick={() => handleSelectProxy(pool.id)} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-zinc-700 ${boundProxyPoolId === pool.id ? 'text-primary-400 font-medium' : 'text-zinc-300'}`}>{pool.name}</button>
                  ))}
                </div>
              )}
            </div>
          )}
          <button onClick={onEdit} className="flex flex-col items-center px-2 py-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-primary-400">
            <Edit2 size={14} />
            <span className="text-[10px] leading-tight">Edit</span>
          </button>
          {onTest && (
            <button
              onClick={onTest}
              disabled={testing}
              className={`flex flex-col items-center px-2 py-1 rounded hover:bg-zinc-800 transition-colors ${testResult?.valid === true ? 'text-emerald-400' : testResult?.valid === false ? 'text-red-400' : 'text-zinc-500 hover:text-primary-400'} ${testing ? 'opacity-60 cursor-wait' : ''}`}
              title={testResult?.valid === true ? 'Connection OK' : testResult?.valid === false ? (testResult.error || 'Connection failed') : 'Test Connection'}
            >
              {testing ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
              <span className="text-[10px] leading-tight">{testing ? 'Testing...' : 'Test'}</span>
            </button>
          )}
          <button onClick={onDelete} className="flex flex-col items-center px-2 py-1 rounded hover:bg-red-900/20 text-red-500">
            <Trash2 size={14} />
            <span className="text-[10px] leading-tight">Delete</span>
          </button>
        </div>
        <Toggle size="sm" checked={isActive} onChange={onToggleActive} title={isActive ? 'Disable' : 'Enable'} />
      </div>
    </div>
  )
}


/* ════════════════════════════════════════════════════════════════
   AddKeyModal — dynamic form fields per provider
   ════════════════════════════════════════════════════════════════ */
function AddKeyModal({ isOpen, providerId, info, editConnection, onClose, onCreated, proxyPools = [], isCompatible = false, isAnthropicCompatible = false }) {
  const isEdit = !!editConnection
  const isOllamaLocal = providerId === "ollama-local"
  const isCookie = info?.authType === "cookie"
  const isAzure = providerId === "azure"
  const isCloudflareAi = providerId === "cloudflare-ai"
  const catalogEntry = useCatalogStore((s) => s.providers[providerId])
  const providerRegions = catalogEntry?.regions || null
  const defaultRegion = catalogEntry?.defaultRegion || providerRegions?.[0]?.id || ""

  const credentialLabel = isCookie ? "Cookie Value" : "API Key"
  const credentialPlaceholder = isCookie
    ? (providerId === "grok-web" ? "sso=xxxxx... or just the raw value" : "eyJhbGciOi...")
    : ""

  const [name, setName] = useState('')
  const [priority, setPriority] = useState(0)
  const [proxyPoolId, setProxyPoolId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [ollamaHostUrl, setOllamaHostUrl] = useState('')
  const [azureData, setAzureData] = useState({ azureEndpoint: "", apiVersion: "2024-10-01-preview", deployment: "", organization: "" })
  const [cloudflareData, setCloudflareData] = useState({ accountId: "" })
  const [region, setRegion] = useState(defaultRegion)
  const [defaultModel, setDefaultModel] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [creating, setCreating] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState(null)
  const [skipValidation, setSkipValidation] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isOpen) {
      if (editConnection) {
        setName(editConnection.name || '')
        setPriority(editConnection.priority ?? 0)
        setProxyPoolId(editConnection.proxy_pool_id || '')
        setApiKey('')
        setBaseUrl(editConnection.base_url || '')
        setDefaultModel(editConnection.default_model || '')
        const ps = editConnection.providerSpecificData || editConnection.provider_specific || {}
        setOllamaHostUrl(ps.baseUrl || editConnection.base_url || '')
        setAzureData({
          azureEndpoint: ps.azureEndpoint || '',
          apiVersion: ps.apiVersion || '2024-10-01-preview',
          deployment: ps.deployment || '',
          organization: ps.organization || '',
        })
        setCloudflareData({ accountId: ps.accountId || '' })
        setRegion(ps.region || defaultRegion)
      } else {
        setName('')
        setPriority(0)
        setProxyPoolId('')
        setApiKey('')
        setBaseUrl('')
        setDefaultModel('')
        setOllamaHostUrl('')
        setAzureData({ azureEndpoint: "", apiVersion: "2024-10-01-preview", deployment: "", organization: "" })
        setCloudflareData({ accountId: "" })
        setRegion(defaultRegion)
      }
      setValidationResult(null)
      setSkipValidation(false)
      setShowApiKey(false)
      setError('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, providerId, editConnection])

  const buildProviderSpecificData = () => {
    if (isOllamaLocal && ollamaHostUrl.trim()) {
      return { baseUrl: ollamaHostUrl.trim() }
    }
    if (isAzure) {
      const data = {}
      if (azureData.azureEndpoint) data.azureEndpoint = azureData.azureEndpoint
      if (azureData.apiVersion) data.apiVersion = azureData.apiVersion
      if (azureData.deployment) data.deployment = azureData.deployment
      if (azureData.organization) data.organization = azureData.organization
      return Object.keys(data).length > 0 ? data : undefined
    }
    if (isCloudflareAi) {
      return { accountId: cloudflareData.accountId }
    }
    if (providerRegions && region) {
      return { region }
    }
    return undefined
  }

  const handleValidate = async () => {
    setValidating(true)
    setValidationResult(null)
    try {
      const res = await providersApi.validateProvider({
        provider: providerId,
        apiKey: apiKey.trim(),
        baseUrl: isOllamaLocal ? (ollamaHostUrl.trim() || undefined) : (baseUrl.trim() || undefined),
        providerSpecificData: buildProviderSpecificData(),
      })
      setValidationResult(res.data)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Validation request failed'
      setValidationResult({ valid: false, error: msg })
    } finally {
      setValidating(false)
    }
  }

  const handleSave = async () => {
    if (!providerId) return
    if (!isOllamaLocal && !apiKey.trim() && !isEdit) return
    if (!isOllamaLocal && !name.trim() && !isEdit) return
    if (isCompatible && !defaultModel.trim()) return

    setCreating(true)
    setError('')
    try {
      if (isEdit) {
        const updateData = {
          name: name.trim() || editConnection.name,
          baseUrl: baseUrl.trim() || undefined,
          providerSpecificData: buildProviderSpecificData(),
          priority: priority,
          proxyPoolId: proxyPoolId || null,
          defaultModel: isCompatible ? defaultModel.trim() : undefined,
        }
        if (apiKey.trim()) {
          updateData.apiKey = apiKey.trim()
        }
        await providersApi.updateProvider(editConnection.id, updateData)
      } else {
        await providersApi.createProvider({
          provider: providerId,
          apiKey: isOllamaLocal ? '' : apiKey.trim(),
          auth_type: isCookie ? 'cookie' : 'apikey',
          name: name.trim() || (isOllamaLocal ? "Ollama Local" : null),
          baseUrl: baseUrl.trim() || undefined,
          providerSpecificData: buildProviderSpecificData(),
          priority: priority,
          proxyPoolId: proxyPoolId || null,
          defaultModel: isCompatible ? defaultModel.trim() : undefined,
        })
      }
      await onCreated()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to save'
      setError(msg)
    } finally {
      setCreating(false)
    }
  }

  const handleClose = () => {
    onClose()
    setValidationResult(null)
    setSkipValidation(false)
    setError('')
  }

  const submitDisabled = creating
    || (!isOllamaLocal && !isEdit && (!name.trim() || !apiKey.trim()))
    || (isCompatible && !defaultModel.trim())
    || (isAzure && !isEdit && (!azureData.azureEndpoint || !azureData.deployment || !azureData.organization))
    || (isCloudflareAi && !isEdit && !cloudflareData.accountId)

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEdit ? `Edit ${info?.name || ''} Connection` : `Add ${info?.name || ''} ${credentialLabel}`}
      className="max-w-xl"
    >
      <div className="space-y-4">
        <Input
          label="Name *"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={isOllamaLocal ? "Ollama Local" : "Production Key"}
          hint={!isOllamaLocal && !isEdit ? 'Required — e.g. Production, Personal, Team' : undefined}
        />

        {isOllamaLocal && (
          <>
            <div className="flex gap-2">
              <Input
                label="Host URL"
                value={ollamaHostUrl}
                onChange={(e) => setOllamaHostUrl(e.target.value)}
                placeholder="http://localhost:11434"
                className="flex-1"
              />
              <div className="pt-6 shrink-0">
                <Button onClick={handleValidate} disabled={validating || creating} variant="secondary">
                  {validating ? "Checking..." : "Check"}
                </Button>
              </div>
            </div>
            <p className="text-xs text-zinc-400">
              Leave blank to use <code className="text-zinc-300">http://localhost:11434</code>. For remote Ollama, enter the host URL.
            </p>
          </>
        )}

        {!isOllamaLocal && (
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Input
                label={credentialLabel}
                type={isCookie ? "text" : (showApiKey ? "text" : "password")}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={isEdit ? "(leave empty to keep current)" : (credentialPlaceholder || "sk-...")}
              />
              {!isCookie && (
                <button
                  type="button"
                  onClick={() => setShowApiKey((v) => !v)}
                  className="absolute right-3 top-[34px] text-zinc-500 hover:text-zinc-300"
                >
                  {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              )}
            </div>
            <div className="pt-6 shrink-0">
              <Button onClick={handleValidate} disabled={!apiKey.trim() || validating || creating} variant="secondary">
                {validating ? "Checking..." : "Check"}
              </Button>
            </div>
          </div>
        )}

        {isCookie && info?.authHint && (
          <p className="text-xs text-zinc-400">
            {info.authHint}
            {info.website && (
              <>
                {" "}
                <a href={info.website} target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">
                  Open {info.website.replace(/^https?:\/\//, "")}
                </a>
              </>
            )}
          </p>
        )}

        {providerRegions && (
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Region</label>
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              {providerRegions.map((r) => (
                <option key={r.id} value={r.id}>{r.label}</option>
              ))}
            </select>
          </div>
        )}

        {isCompatible && (
          <Input
            label="Default Model"
            value={defaultModel}
            onChange={(e) => setDefaultModel(e.target.value)}
            placeholder={isAnthropicCompatible ? "claude-3-5-sonnet-latest" : "gpt-4o-mini"}
          />
        )}

        {isCompatible && (
          <div>
            <Input
              label="Base URL"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={editConnection?.base_url || "https://api.example.com/v1"}
            />
            <p className="text-xs text-zinc-400 mt-1">
              Enter the model ID exactly as your compatible endpoint expects it. This model will be saved as the connection default.
            </p>
          </div>
        )}

        {validationResult && (
          <div className={`rounded-lg border p-3 ${validationResult.valid ? 'bg-emerald-950/30 border-emerald-700/40' : 'bg-red-950/30 border-red-700/40'}`}>
            <div className="flex items-center gap-2">
              {validationResult.valid ? (
                <>
                  <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  <span className="text-sm text-emerald-300">
                    Connection verified
                    {validationResult.models?.length > 0 && (
                      <span className="text-emerald-400"> — {validationResult.models.length} model{validationResult.models.length !== 1 ? 's' : ''} found</span>
                    )}
                  </span>
                </>
              ) : (
                <>
                  <AlertCircle size={16} className="text-red-400 shrink-0" />
                  <span className="text-sm text-red-300">{validationResult.error}</span>
                </>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border p-3 bg-red-950/30 border-red-700/40">
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-red-400 shrink-0" />
              <span className="text-sm text-red-300">{error}</span>
            </div>
          </div>
        )}

        {isCloudflareAi && (
          <div className="bg-zinc-900/50 p-4 rounded-lg border border-zinc-700/40">
            <h3 className="font-semibold mb-3 text-sm text-zinc-200">Cloudflare Workers AI</h3>
            <Input
              label="Account ID"
              value={cloudflareData.accountId}
              onChange={(e) => setCloudflareData({ ...cloudflareData, accountId: e.target.value })}
              placeholder="abc123def456..."
            />
            <p className="text-xs text-zinc-400 mt-2">
              Find your Account ID in the right sidebar of <a href="https://dash.cloudflare.com" target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">dash.cloudflare.com</a>
            </p>
          </div>
        )}

        {isAzure && (
          <div className="bg-zinc-900/50 p-4 rounded-lg border border-zinc-700/40">
            <h3 className="font-semibold mb-3 text-sm text-zinc-200">Azure OpenAI Configuration</h3>
            <div className="flex flex-col gap-3">
              <Input
                label="Azure Endpoint"
                value={azureData.azureEndpoint}
                onChange={(e) => setAzureData({ ...azureData, azureEndpoint: e.target.value })}
                placeholder="https://your-resource.openai.azure.com"
              />
              <Input
                label="Deployment Name"
                value={azureData.deployment}
                onChange={(e) => setAzureData({ ...azureData, deployment: e.target.value })}
                placeholder="gpt-4"
              />
              <Input
                label="API Version"
                value={azureData.apiVersion}
                onChange={(e) => setAzureData({ ...azureData, apiVersion: e.target.value })}
                placeholder="2024-10-01-preview"
              />
              <Input
                label="Organization"
                value={azureData.organization}
                onChange={(e) => setAzureData({ ...azureData, organization: e.target.value })}
                placeholder="Organization ID"
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Priority</label>
            <input
              type="number"
              min={0}
              value={priority}
              onChange={(e) => setPriority(parseInt(e.target.value, 10) || 0)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            <p className="text-xs text-zinc-500 mt-1">Lower = higher priority</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">Proxy Pool</label>
            <select
              value={proxyPoolId}
              onChange={(e) => setProxyPoolId(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            >
              <option value="">None</option>
              {proxyPools.map((pool) => (
                <option key={pool.id} value={pool.id}>{pool.name}</option>
              ))}
            </select>
          </div>
        </div>

        {validationResult && !validationResult.valid && (
          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="skip-validation"
              checked={skipValidation}
              onChange={(e) => setSkipValidation(e.target.checked)}
              className="rounded border-zinc-600 bg-zinc-800 text-primary-500 focus:ring-primary-500"
            />
            <label htmlFor="skip-validation" className="text-xs text-zinc-500 cursor-pointer">
              Save anyway (connection may not work)
            </label>
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button
            variant="secondary"
            onClick={handleValidate}
            disabled={validating || (!isOllamaLocal && !apiKey.trim())}
          >
            {validating ? (
              <><Loader2 size={14} className="animate-spin" /> Testing...</>
            ) : (
              <><Wifi size={14} /> Test Connection</>
            )}
          </Button>

          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={handleClose}>Cancel</Button>
            <Button
              onClick={handleSave}
              disabled={submitDisabled && !skipValidation}
            >
              {creating ? (isEdit ? 'Saving...' : 'Adding...') : (isEdit ? 'Save' : 'Add Connection')}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}


/* ════════════════════════════════════════════════════════════════
   PassthroughModelsSection — for OpenRouter-style passthrough
   ════════════════════════════════════════════════════════════════ */
function PassthroughModelsSection({ providerAlias, modelAliases, copied, onCopy, onSetAlias, onDeleteAlias, suggestedModels = [] }) {
  const [newModel, setNewModel] = useState('')
  const [adding, setAdding] = useState(false)

  const providerAliases = Object.entries(modelAliases).filter(
    ([, model]) => model.startsWith(`${providerAlias}/`)
  )

  const allModels = providerAliases.map(([alias, fullModel]) => ({
    modelId: fullModel.replace(`${providerAlias}/`, ''),
    fullModel,
    alias,
  }))

  // Filter suggested models: only show ones not already added
  const addedFullModels = new Set(Object.values(modelAliases))
  const notAddedSuggestions = suggestedModels.filter(
    (m) => !addedFullModels.has(`${providerAlias}/${m.id}`)
  )

  const generateDefaultAlias = (modelId) => {
    const parts = modelId.split('/')
    return parts[parts.length - 1]
  }

  const handleAdd = async () => {
    if (!newModel.trim() || adding) return
    const modelId = newModel.trim()
    const defaultAlias = generateDefaultAlias(modelId)
    if (modelAliases[defaultAlias]) {
      alert(`Alias "${defaultAlias}" already exists.`)
      return
    }
    setAdding(true)
    try {
      await onSetAlias(modelId, defaultAlias)
      setNewModel('')
    } catch (error) {
      console.log('Error adding model:', error)
    } finally {
      setAdding(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-zinc-400">
        OpenRouter supports any model. Add models and create aliases for quick access.
      </p>

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <label htmlFor="new-model-input" className="text-xs text-zinc-500 mb-1 block">Model ID (from OpenRouter)</label>
          <input
            id="new-model-input"
            type="text"
            value={newModel}
            onChange={(e) => setNewModel(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            placeholder="anthropic/claude-3-opus"
            className="w-full px-3 py-2 text-sm border border-zinc-700 rounded-lg bg-zinc-800/50 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <Button size="sm" onClick={handleAdd} disabled={!newModel.trim() || adding}>
          <Plus size={14} /> {adding ? 'Adding...' : 'Add'}
        </Button>
      </div>

      {/* Suggested models from provider API */}
      {notAddedSuggestions.length > 0 && (
        <div className="w-full">
          <p className="text-xs text-zinc-500 mb-2">Suggested models (click to add):</p>
          <div className="flex flex-wrap gap-2">
            {notAddedSuggestions.map((m) => (
              <button
                key={m.id}
                onClick={async () => {
                  const alias = m.id.split('/').pop()
                  await onSetAlias(m.id, alias, providerAlias)
                }}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-zinc-700 text-xs text-zinc-400 hover:text-primary-400 hover:border-primary-500/40 hover:bg-primary-500/5 transition-colors"
                title={m.name || m.id}
              >
                <Plus size={12} />
                {m.name || m.id.split('/').pop()}
              </button>
            ))}
          </div>
        </div>
      )}

      {allModels.length > 0 && (
        <div className="flex flex-col gap-3">
          {allModels.map(({ modelId, fullModel, alias }) => (
            <div key={fullModel} className="flex items-center gap-3 p-3 rounded-lg border border-zinc-700 hover:bg-zinc-800/40">
              <Beaker size={16} className="text-zinc-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{modelId}</p>
                <div className="flex items-center gap-1 mt-1">
                  <code className="text-xs text-zinc-500 font-mono bg-zinc-800 px-1.5 py-0.5 rounded">{fullModel}</code>
                  <button
                    onClick={() => onCopy(fullModel, `model-${modelId}`)}
                    className="p-0.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400 cursor-pointer"
                  >
                    {copied === `model-${modelId}` ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </div>
              <button onClick={() => onDeleteAlias(alias)} className="p-1 hover:bg-red-900/20 rounded text-red-500" title="Remove model">
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


/* ════════════════════════════════════════════════════════════════
   AddCustomModelModal — test-before-add modal
   ════════════════════════════════════════════════════════════════ */
function AddCustomModelModal({ isOpen, providerAlias, providerDisplayAlias, onSave, onClose }) {
  const [modelId, setModelId] = useState('')
  const [testStatus, setTestStatus] = useState(null)
  const [testError, setTestError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) { setModelId(''); setTestStatus(null); setTestError('') }
  }, [isOpen])

  const stripAlias = (id) => {
    const prefix = `${providerAlias}/`
    return id.startsWith(prefix) ? id.slice(prefix.length) : id
  }

  const handleTest = async () => {
    const cleanId = stripAlias(modelId.trim())
    if (!cleanId) return
    setTestStatus('testing')
    setTestError('')
    try {
      const { default: client } = await import('../api/client')
      const res = await client.post('/models/test', { model: `${providerAlias}/${cleanId}` })
      setTestStatus(res.data?.ok ? 'ok' : 'error')
      setTestError(res.data?.error || '')
    } catch (err) {
      setTestStatus('error')
      setTestError(err.message || 'Test request failed')
    }
  }

  const handleSave = async () => {
    const cleanId = stripAlias(modelId.trim())
    if (!cleanId || saving) return
    setSaving(true)
    try { await onSave(cleanId) }
    finally { setSaving(false) }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Custom Model">
      <div className="flex flex-col gap-4">
        <div>
          <label className="text-sm font-medium mb-1.5 block">Model ID</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={modelId}
              onChange={(e) => { setModelId(e.target.value); setTestStatus(null); setTestError('') }}
              onKeyDown={(e) => e.key === 'Enter' && handleTest()}
              placeholder="e.g. claude-opus-4-5"
              className="flex-1 px-3 py-2 text-sm border border-zinc-700 rounded-lg bg-zinc-800/50 text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              autoFocus
            />
            <Button variant="secondary" onClick={handleTest} disabled={!modelId.trim() || testStatus === 'testing'}>
              {testStatus === 'testing' ? <Loader2 size={14} className="animate-spin" /> : <Beaker size={14} />}
              {testStatus === 'testing' ? 'Testing...' : 'Test'}
            </Button>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Sent to provider as: <code className="font-mono bg-zinc-800 px-1 rounded">{stripAlias(modelId.trim()) || 'model-id'}</code>
          </p>
        </div>

        {testStatus === 'ok' && (
          <div className="flex items-center gap-2 text-sm text-emerald-400">
            <CheckCircle2 size={16} /> Model is reachable
          </div>
        )}
        {testStatus === 'error' && (
          <div className="flex items-start gap-2 text-sm text-red-400">
            <AlertCircle size={16} className="shrink-0" />
            <span>{testError || 'Model not reachable'}</span>
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button onClick={onClose} variant="ghost" className="flex-1">Cancel</Button>
          <Button onClick={handleSave} className="flex-1" disabled={!modelId.trim() || saving}>
            {saving ? 'Adding...' : 'Add Model'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}


/* ════════════════════════════════════════════════════════════════
   ModelRow — single model chip with copy, test, alias, disable
   ════════════════════════════════════════════════════════════════ */
function ModelRow({ model, fullModel, alias, copied, onCopy, onSetAlias, onDeleteAlias, testStatus, onTest, isTesting, isCustom, isFree, onDisable, modelType, onTypeChange }) {
  const [editingAlias, setEditingAlias] = useState(false)
  const [aliasValue, setAliasValue] = useState(alias || '')
  const [showTypeDropdown, setShowTypeDropdown] = useState(false)
  const typeDropdownRef = useRef(null)

  const borderColor = testStatus === 'ok' ? 'border-emerald-500/40' : testStatus === 'error' ? 'border-red-500/40' : 'border-zinc-700'

  // Close type dropdown on outside click
  useEffect(() => {
    if (!showTypeDropdown) return
    const handler = (e) => {
      if (typeDropdownRef.current && !typeDropdownRef.current.contains(e.target))
        setShowTypeDropdown(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showTypeDropdown])

  return (
    <div className={`inline-flex items-center gap-3 rounded-lg border ${borderColor} px-3 py-2 hover:bg-zinc-800/40`}>
      <span className="text-zinc-500">
        {testStatus === 'ok' ? <CheckCircle2 size={16} className="text-emerald-500" /> : testStatus === 'error' ? <AlertCircle size={16} className="text-red-500" /> : <Beaker size={16} />}
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="text-xs font-medium text-zinc-200 truncate">{model.id || model.name || model}</p>
          {modelType && onTypeChange && (
            <div className="relative shrink-0" ref={typeDropdownRef}>
              <button
                onClick={(e) => { e.stopPropagation(); setShowTypeDropdown(v => !v) }}
                className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors cursor-pointer ${TYPE_BADGE_STYLES[modelType] || TYPE_BADGE_STYLES.llm}`}
              >
                {modelType}
                <ChevronDown size={10} />
              </button>
              {showTypeDropdown && (
                <div className="absolute left-0 top-full mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg py-1 min-w-[100px]">
                  {['llm', 'embedding', 'tts', 'stt', 'image', 'webSearch', 'webFetch'].map(t => (
                    <button
                      key={t}
                      onClick={(e) => { e.stopPropagation(); onTypeChange(t); setShowTypeDropdown(false) }}
                      className={`w-full text-left px-3 py-1.5 text-xs hover:bg-zinc-700 ${modelType === t ? 'text-primary-400 font-medium' : 'text-zinc-300'}`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        {model.context_length && (
          <p className="text-[10px] text-zinc-500">{(model.context_length / 1000).toFixed(0)}k ctx</p>
        )}
        <div className="flex items-center gap-1 mt-0.5">
          <code className="text-[10px] text-zinc-500 font-mono bg-zinc-800 px-1 py-0.5 rounded truncate max-w-[180px]">{fullModel}</code>
          <button onClick={() => onCopy(fullModel, `model-${model.id || model}`)} className="p-0.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400 cursor-pointer">
            {copied === `model-${model.id || model}` ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </div>

      {alias && !editingAlias && (
        <span className="text-[10px] text-primary-400 font-mono bg-primary-500/10 px-1.5 py-0.5 rounded cursor-pointer" onClick={() => setEditingAlias(true)} title="Click to edit alias">
          @{alias}
        </span>
      )}

      {onTest && (
        <button onClick={onTest} disabled={isTesting} className="p-1 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400" title="Test model">
          <Beaker size={12} className={isTesting ? 'animate-spin' : ''} />
        </button>
      )}
      {onDisable && (
        <button onClick={onDisable} className="p-1 hover:bg-zinc-800 rounded text-zinc-500" title="Disable model">
          <Ban size={12} />
        </button>
      )}
      {onDeleteAlias && isCustom && (
        <button onClick={onDeleteAlias} className="p-1 hover:bg-red-900/20 rounded text-red-500" title="Remove model">
          <Trash2 size={12} />
        </button>
      )}
    </div>
  )
}


/* ════════════════════════════════════════════════════════════════
   ChatTestPlayground — real API test for chat completions
   ════════════════════════════════════════════════════════════════ */
function ChatTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [selectedModel, setSelectedModel] = useState('')
  const [messages, setMessages] = useState([{ role: 'user', content: 'Hello, how are you?' }])
  const [temperature, setTemperature] = useState(0.7)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [stream, setStream] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [availableModels, setAvailableModels] = useState([])
  const resultRef = useRef(null)

  useEffect(() => {
    import('../api/client').then(({ default: client }) => {
      client.get(`/providers/${providerId}/models/list`)
        .then(res => {
          const models = (res.data?.models || []).map(m => ({ id: `${providerAlias}/${m.id}`, type: m.type }))
          setAvailableModels(models)
          if (models.length > 0 && !selectedModel) setSelectedModel(models[0].id)
        })
        .catch(() => {})
    })
  }, [providerId, providerAlias])

  const buildBody = () => ({
    model: selectedModel || `${providerId}/default`,
    messages: messages.filter(m => m.content.trim()),
    temperature,
    max_tokens: maxTokens,
    stream,
  })

  const endpoint = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:9000'
  const curlBody = JSON.stringify(buildBody(), null, 2).replace(/'/g, "'\\''")
  const curlSnippet = `curl -X POST ${endpoint}/v1/chat/completions \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer ${token || 'YOUR_TOKEN'}" \\\n  -d '${curlBody}'`

  const handleRun = async () => {
    if (!messages.some(m => m.content.trim())) return
    setRunning(true); setError(''); setResult(null); setLatency(null)
    const start = Date.now()
    try {
      const res = await fetch('/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token || ''}` },
        body: JSON.stringify(buildBody()),
      })
      if (stream) {
        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let streamed = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop()
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data === '[DONE]') continue
              try {
                const parsed = JSON.parse(data)
                const content = parsed.choices?.[0]?.delta?.content || ''
                streamed += content
                setResult({ streamed_text: streamed })
              } catch {}
            }
          }
        }
        setLatency(Date.now() - start)
      } else {
        const data = await res.json()
        setLatency(Date.now() - start)
        if (!res.ok) throw new Error(data.error?.message || `HTTP ${res.status}`)
        setResult(data)
      }
    } catch (e) { setError(e.message); setLatency(Date.now() - start) } finally { setRunning(false) }
  }

  const addMessage = () => setMessages([...messages, { role: 'user', content: '' }])
  const removeMessage = (idx) => setMessages(messages.filter((_, i) => i !== idx))
  const updateMessage = (idx, field, value) => {
    const updated = [...messages]
    updated[idx] = { ...updated[idx], [field]: value }
    setMessages(updated)
  }

  return (
    <Card className="bg-zinc-900/50 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <MessageSquare size={16} className="text-primary-400" />
          Chat Completions Test Playground
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
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-zinc-400">Messages</label>
            <button onClick={addMessage} className="text-xs text-primary-400 hover:text-primary-300 cursor-pointer">+ Add</button>
          </div>
          <div className="space-y-2">
            {messages.map((msg, idx) => (
              <div key={idx} className="flex gap-2">
                <select value={msg.role} onChange={(e) => updateMessage(idx, 'role', e.target.value)}
                  className="w-24 bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 text-xs text-zinc-200">
                  <option value="system">system</option>
                  <option value="user">user</option>
                  <option value="assistant">assistant</option>
                </select>
                <input value={msg.content} onChange={(e) => updateMessage(idx, 'content', e.target.value)}
                  placeholder="Message content..."
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200" />
                {messages.length > 1 && (
                  <button onClick={() => removeMessage(idx)} className="text-zinc-500 hover:text-red-400 cursor-pointer">
                    <X size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Temperature</label>
            <input type="number" value={temperature} onChange={(e) => setTemperature(Number(e.target.value) || 0)} min={0} max={2} step={0.1}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" />
          </div>
          <div>
            <label className="text-xs text-zinc-400 mb-1 block">Max Tokens</label>
            <input type="number" value={maxTokens} onChange={(e) => setMaxTokens(Number(e.target.value) || 256)} min={1} max={128000}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200" />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={stream} onChange={(e) => setStream(e.target.checked)} className="rounded border-zinc-600" />
              <span className="text-xs text-zinc-400">Stream</span>
            </label>
          </div>
        </div>

        <div className="flex gap-2">
          <Button size="sm" onClick={handleRun} disabled={running || !messages.some(m => m.content.trim())}>
            {running ? <Loader2 size={14} className="animate-spin mr-1" /> : <Play size={14} className="mr-1" />}
            Run
          </Button>
          {latency && <span className="text-xs text-zinc-500 self-center">{latency}ms</span>}
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs text-zinc-400">cURL</label>
            <button onClick={() => { copyToClipboard(curlSnippet).then(ok => { if (ok) { setCopiedCurl(true); setTimeout(() => setCopiedCurl(false), 2000) } }) }}
              className="text-xs text-zinc-500 hover:text-primary-400 cursor-pointer">{copiedCurl ? 'Copied!' : 'Copy'}</button>
          </div>
          <pre className="bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap break-all max-h-48 overflow-y-auto">{curlSnippet}</pre>
        </div>

        {error && <div className="text-xs text-red-400 bg-red-500/10 rounded-lg p-3">{error}</div>}
        {result && (
          <div ref={resultRef}>
            <label className="text-xs text-zinc-400 mb-1 block">Response</label>
            {result.streamed_text ? (
              <pre className="bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">{result.streamed_text}</pre>
            ) : (
              <pre className="bg-zinc-800/80 rounded-lg p-3 text-xs text-zinc-300 overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">{JSON.stringify(result, null, 2)}</pre>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}


/* ════════════════════════════════════════════════════════════════
   Main ProviderDetailPage
   ════════════════════════════════════════════════════════════════ */
export default function ProviderDetailPage() {
  const { providerId: rawProviderId } = useParams()
  const catalogStore = useCatalogStore()
  const providerId = catalogStore.resolveProviderId(rawProviderId)
  const navigate = useNavigate()
  const info = catalogStore.providers[providerId]

  // Provider auth type detection
  const isOAuth = info?.authType === 'oauth' || info?.authType === 'free'
  const isFreeNoAuth = info?.noAuth === true
  const isWebCookie = info?.authType === 'cookie'

  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [providerNode, setProviderNode] = useState(null)
  const [proxyPools, setProxyPools] = useState([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [showOAuthModal, setShowOAuthModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showEditNodeModal, setShowEditNodeModal] = useState(false)
  const [showBulkProxyModal, setShowBulkProxyModal] = useState(false)
  const [selectedConnection, setSelectedConnection] = useState(null)
  const [confirmState, setConfirmState] = useState(null)
  const [addConnectionError, setAddConnectionError] = useState('')
  const [testingConnectionId, setTestingConnectionId] = useState(null)
  const [testResults, setTestResults] = useState({})
  const [connectingNoAuth, setConnectingNoAuth] = useState(false)

  // Models state
  const [models, setModels] = useState([])
  const [newModel, setNewModel] = useState('')
  const [showAddCustomModel, setShowAddCustomModel] = useState(false)
  const [modelAliases, setModelAliases] = useState({})
  const [disabledModelIds, setDisabledModelIds] = useState([])
  const [modelTestResults, setModelTestResults] = useState({})
  const [testingModelId, setTestingModelId] = useState(null)
  const [modelsTestError, setModelsTestError] = useState('')
  const [suggestedModels, setSuggestedModels] = useState([])
  const [modelSearchQuery, setModelSearchQuery] = useState('')
  const [copied, setCopied] = useState(null)
  const [enabledModelIds, setEnabledModelIds] = useState(new Set())
  const [fetchingModels, setFetchingModels] = useState(false)
  const [clearingModels, setClearingModels] = useState(false)
  const [fetchedSuggestions, setFetchedSuggestions] = useState([])
  const [fetchingSuggestions, setFetchingSuggestions] = useState(false)
  const [suggestionsError, setSuggestionsError] = useState(false)

  // Provider strategy
  const [providerStrategy, setProviderStrategy] = useState(null)
  const [providerStickyLimit, setProviderStickyLimit] = useState('1')
  const [thinkingMode, setThinkingMode] = useState('auto')

  // Bulk proxy
  const [selectedConnectionIds, setSelectedConnectionIds] = useState([])
  const [bulkProxyPoolId, setBulkProxyPoolId] = useState('__none__')
  const [bulkUpdatingProxy, setBulkUpdatingProxy] = useState(false)

  // Header image
  const [headerImgError, setHeaderImgError] = useState(false)

  // Determine if this is a compatible provider
  const isCompatible = providerNode && COMPATIBLE_TYPES.has(providerNode.type)
  const isAnthropicCompatible = providerNode?.type === 'anthropic-compatible'
  const isOpenAICompatible = providerNode?.type === 'openai-compatible'
  // Provider alias for model storage
  const providerAlias = catalogStore.getProviderAlias(providerId)
  const providerStorageAlias = isCompatible ? providerId : providerAlias
  const providerDisplayAlias = isCompatible ? (providerNode?.prefix || providerId) : providerAlias

  // Thinking config — safe fallback
  const THINKING_EXTENDED_DEFAULT = { options: ["auto", "on", "off"], defaultMode: "auto", defaultBudgetTokens: 10000 }
  const thinkingConfig = info?.thinkingConfig || THINKING_EXTENDED_DEFAULT

  // Build display info from provider node or PROVIDERS constant
  // NOTE: Must be safe even when both info AND providerNode are null (edge case)
  const displayInfo = (() => {
    if (isCompatible && providerNode) {
      return {
        name: providerNode.name || (isAnthropicCompatible ? 'Anthropic Compatible' : 'OpenAI Compatible'),
        color: isAnthropicCompatible ? '#D97757' : '#10A37F',
        icon: isAnthropicCompatible ? 'AC' : 'OC',
      }
    }
    if (info) return info
    // Fallback for unknown providers (shouldn't reach here due to not-found guard)
    return { name: 'Unknown Provider', color: '#71717A', icon: '?' }
  })()

  // ── Clipboard helper ──
  const handleCopy = useCallback((text, id) => {
    copyToClipboard(text).then((ok) => {
      if (ok) {
        setCopied(id)
        setTimeout(() => setCopied(null), 2000)
      }
    })
  }, [])

  // ── Model type helpers ──
  const getModelType = useCallback((modelId) => {
    // Try to get from connection data (modelTypes user override)
    for (const conn of connections) {
      const ps = conn.providerSpecificData || conn.provider_specific || {}
      const modelTypes = ps.modelTypes || {}
      if (modelTypes[modelId]) return modelTypes[modelId]
    }
    // Try to get from model objects with type field
    for (const conn of connections) {
      const connModels = conn.models || []
      const found = connModels.find(m => (typeof m === 'string' ? m : m.id) === modelId)
      if (found && typeof found === 'object' && found.type) return found.type
    }
    // Fallback to client-side inference
    return inferModelType(modelId)
  }, [connections])

  // ── Fetch model aliases ──
  const fetchAliases = useCallback(async () => {
    try {
      const { default: client } = await import('../api/client')
      const res = await client.get('/models/alias')
      if (res.data?.aliases) setModelAliases(res.data.aliases)
    } catch (error) {
      // Alias endpoint may not exist yet
      console.log('Aliases not available:', error.message)
    }
  }, [])

  // ── Fetch disabled models ──
  const fetchDisabledModels = useCallback(async () => {
    try {
      const { default: client } = await import('../api/client')
      const res = await client.get(`/models/disabled`, { params: { providerAlias: providerStorageAlias } })
      if (res.data?.ids) setDisabledModelIds(res.data.ids)
    } catch (error) {
      // Disabled models endpoint may not exist yet
      console.log('Disabled models not available:', error.message)
    }
  }, [providerStorageAlias])

  // ── Fetch connections + nodes + pools + settings ──
  const fetchConnections = useCallback(async () => {
    try {
      const [connRes, proxyRes] = await Promise.all([
        providersApi.getProviders(),
        proxyPoolsApi.getAll(),
      ])
      const allConns = connRes.data || []
      const filtered = allConns.filter((c) => c.provider === providerId)
      filtered.sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0))
      setConnections(filtered)
      setProxyPools((proxyRes.data || []).filter((p) => p.is_active !== false))

      // Derive models from ALL connections (union)
      if (filtered.length > 0) {
        const allModels = new Set()
        filtered.forEach(c => (c.models || []).forEach(m => allModels.add(typeof m === 'string' ? m : m.id)))
        const mergedModels = [...allModels]
        setModels(mergedModels)
        setEnabledModelIds(new Set(mergedModels))
      } else {
        setModels([])
        setEnabledModelIds(new Set())
      }

      // Fetch provider nodes
      try {
        const nodesRes = await providersApi.getProviderNodes()
        const node = (nodesRes.data || []).find((n) => n.id === providerId) || null
        setProviderNode(node)
      } catch {
        // Provider nodes may not be available
      }

      // Fetch settings for strategy
      try {
        const settingsRes = await settingsApi.get()
        const settingsData = settingsRes.data || {}
        const strategies = settingsData.provider_strategies || settingsData.providerStrategies || {}
        const override = strategies[providerId] || {}
        setProviderStrategy(override.fallback_strategy || override.fallbackStrategy || null)
        const sticky = override.sticky_round_robin_limit ?? override.stickyRoundRobinLimit
        setProviderStickyLimit(sticky != null ? String(sticky) : '1')
        // Load per-provider thinking config
        const thinkingCfg = (settingsData.provider_thinking || settingsData.providerThinking || {})[providerId] || {}
        setThinkingMode(thinkingCfg.mode || 'auto')
      } catch {
        // Settings may not be available
      }
    } catch (err) {
      console.error('Failed to fetch connections:', err)
    } finally {
      setLoading(false)
    }
  }, [providerId])

  const handleChangeModelType = useCallback(async (modelId, newType) => {
    const connId = connections[0]?.id
    if (!connId) return
    try {
      await providersApi.changeModelType(connId, modelId, newType)
      await fetchConnections()
    } catch (err) {
      console.error('Failed to change model type:', err)
    }
  }, [connections, fetchConnections])

  // ── Save provider strategy ──
  const saveProviderStrategy = async (strategy, stickyLimit) => {
    try {
      const settingsRes = await settingsApi.get()
      const current = (settingsRes.data || {}).providerStrategies || (settingsRes.data || {}).provider_strategies || {}
      const override = {}
      if (strategy) override.fallbackStrategy = strategy
      if (strategy === 'round-robin' && stickyLimit !== '') {
        override.stickyRoundRobinLimit = Number(stickyLimit) || 3
      }
      const updated = { ...current }
      if (Object.keys(override).length === 0) {
        delete updated[providerId]
      } else {
        updated[providerId] = override
      }
      await settingsApi.update({ providerStrategies: updated })
    } catch (error) {
      console.log('Error saving provider strategy:', error)
    }
  }

  const handleStrategyChange = (newStrategy) => {
    const strategy = newStrategy === 'fill-first' ? null : newStrategy
    if (strategy === 'round-robin' && !providerStickyLimit) setProviderStickyLimit('1')
    setProviderStrategy(strategy)
    saveProviderStrategy(strategy, providerStickyLimit)
  }

  const handleStickyLimitChange = (value) => {
    setProviderStickyLimit(value)
    saveProviderStrategy('round-robin', value)
  }

  // ── Thinking config save ──
  const saveThinkingConfig = async (mode) => {
    try {
      const settingsRes = await settingsApi.get()
      const current = (settingsRes.data || {}).provider_thinking || {}
      const updated = { ...current }
      if (!mode || mode === 'auto') {
        delete updated[providerId]
      } else {
        updated[providerId] = { mode }
      }
      await settingsApi.update({ provider_thinking: updated })
    } catch (error) {
      console.log('Error saving thinking config:', error)
    }
  }

  const handleThinkingModeChange = (mode) => {
    setThinkingMode(mode)
    saveThinkingConfig(mode)
  }

  // ── Auto-save models to all connections ──
  const saveModels = async (newModels) => {
    const previousModels = models
    setModels(newModels)
    try {
      await Promise.all(
        connections.map((c) =>
          providersApi.updateProvider(c.id, { models: newModels })
        )
      )
    } catch (err) {
      console.error('Failed to save models:', err)
      setModels(previousModels)
      setEnabledModelIds(new Set(previousModels.map(m => typeof m === 'string' ? m : m.id)))
    }
  }

  const addModel = (model) => {
    const trimmed = (model || newModel).trim()
    if (!trimmed) return
    const prefixed = trimmed.includes('/') ? trimmed : `${providerId}/${trimmed}`
    if (models.includes(prefixed)) return
    const updated = [...models, prefixed]
    setNewModel('')
    setEnabledModelIds((prev) => new Set([...prev, prefixed]))
    saveModels(updated)
  }

  const removeModel = (idx) => {
    const updated = models.filter((_, i) => i !== idx)
    saveModels(updated)
  }

  // ── Fetch models from provider API (go to suggestions, persist to backend) ──
  const handleFetchModels = async () => {
    if (!connections.length || fetchingModels) return
    setFetchingModels(true)
    try {
      // Use only the first active connection to avoid rate limiting / IP ban
      const activeConn = connections.find(c => c.is_active !== false) || connections[0]
      const res = await providersApi.fetchProviderModels(activeConn.id)
      const fetchedList = res.data?.models || res.data || []
      const fetchedArray = fetchedList.map(m => typeof m === 'string' ? m : m.id)

      // fetchProviderModels already saves to DB for the fetched connection.
      // Only patch OTHER connections to sync models (skip the one already updated).
      const otherConns = connections.filter(c => c.id !== activeConn.id)
      if (otherConns.length > 0) {
        await Promise.all(
          otherConns.map(c => providersApi.updateProvider(c.id, { models: fetchedArray }))
        )
      }

      setSuggestedModels([])
      if (info?.modelsFetcher) {
        fetchSuggestedModels(info.modelsFetcher).then(setSuggestedModels)
      }
      await fetchConnections()
    } catch (err) {
      console.error('Failed to fetch models:', err)
      // Show user-friendly error message
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to fetch models'
      useNotificationStore.getState().addNotification({
        type: 'error',
        title: 'Failed to fetch models',
        message: errorMessage,
      })
    } finally {
      setFetchingModels(false)
    }
  }

  // ── Clear all models ──
  const handleClearModels = async () => {
    if (clearingModels) return
    setClearingModels(true)
    try {
      await Promise.all(
        connections.map((c) =>
          providersApi.clearProviderModels(c.id)
        )
      )
      setModels([])
      setEnabledModelIds(new Set())
      setSuggestedModels([])
      await fetchConnections()
    } catch (err) {
      console.error('Failed to clear models:', err)
    } finally {
      setClearingModels(false)
    }
  }

  // ── Model alias handlers ──
  const handleSetAlias = async (modelId, alias, provAlias = providerAlias) => {
    const fullModel = `${provAlias}/${modelId}`
    try {
      const { default: client } = await import('../api/client')
      await client.put('/models/alias', { model: fullModel, alias })
      await fetchAliases()
    } catch (error) {
      console.log('Error setting alias:', error)
    }
  }

  const handleDeleteAlias = async (alias) => {
    try {
      const { default: client } = await import('../api/client')
      await client.delete(`/models/alias`, { params: { alias } })
      await fetchAliases()
    } catch (error) {
      console.log('Error deleting alias:', error)
    }
  }

  // ── Disabled models handlers ──
  const handleDisableModel = async (modelId) => {
    try {
      const { default: client } = await import('../api/client')
      await client.post('/models/disabled', { providerAlias: providerStorageAlias, ids: [modelId] })
      await fetchDisabledModels()
    } catch (error) {
      console.log('Error disabling model:', error)
    }
  }

  const handleEnableModel = async (modelId) => {
    try {
      const { default: client } = await import('../api/client')
      await client.delete('/models/disabled', { params: { providerAlias: providerStorageAlias, id: modelId } })
      await fetchDisabledModels()
    } catch (error) {
      console.log('Error enabling model:', error)
    }
  }

  const handleDisableAll = (ids) => {
    if (!ids.length) return
    setConfirmState({
      title: 'Disable All Models',
      message: `Disable all ${ids.length} model(s)?`,
      onConfirm: async () => {
        setConfirmState(null)
        try {
          const { default: client } = await import('../api/client')
          await client.post('/models/disabled', { providerAlias: providerStorageAlias, ids })
          await fetchDisabledModels()
        } catch (error) {
          console.log('Error disabling all models:', error)
        }
      }
    })
  }

  const handleEnableAll = async () => {
    try {
      const { default: client } = await import('../api/client')
      await client.delete('/models/disabled', { params: { providerAlias: providerStorageAlias } })
      await fetchDisabledModels()
    } catch (error) {
      console.log('Error enabling all models:', error)
    }
  }

  // ── Model testing ──
  const handleTestModel = async (modelId) => {
    if (testingModelId) return
    setTestingModelId(modelId)
    try {
      const { default: client } = await import('../api/client')
      const res = await client.post('/models/test', { model: `${providerStorageAlias}/${modelId}` })
      setModelTestResults((prev) => ({ ...prev, [modelId]: res.data?.ok ? 'ok' : 'error' }))
      setModelsTestError(res.data?.ok ? '' : (res.data?.error || 'Model not reachable'))
    } catch {
      setModelTestResults((prev) => ({ ...prev, [modelId]: 'error' }))
      setModelsTestError('Network error')
    } finally {
      setTestingModelId(null)
    }
  }

  // ── Connection handlers ──
  const handleSaveApiKey = async (formData) => {
    setAddConnectionError('')
    try {
      await providersApi.createProvider({ provider: providerId, ...formData })
      await fetchConnections()
      setShowAddModal(false)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to save connection'
      setAddConnectionError(msg)
    }
  }

  const handleNoAuthConnect = async () => {
    setConnectingNoAuth(true)
    try {
      await providersApi.createProvider({
        provider: providerId,
        auth_type: 'free',
        noAuth: true,
        priority: 1,
      })
      await fetchConnections()
    } catch (err) {
      console.error('NoAuth connect failed:', err)
    } finally {
      setConnectingNoAuth(false)
    }
  }

  const handleUpdateConnection = async (formData) => {
    try {
      await providersApi.updateProvider(selectedConnection.id, formData)
      await fetchConnections()
      setShowEditModal(false)
    } catch (err) {
      console.error('Failed to update connection:', err)
    }
  }

  const handleToggleActive = async (id, isActive) => {
    setConnections((prev) => prev.map((c) => (c.id === id ? { ...c, is_active: isActive } : c)))
    try {
      await providersApi.updateProvider(id, { is_active: isActive })
    } catch (err) {
      console.error('Failed to toggle:', err)
      await fetchConnections()
    }
  }

  const handleSwapPriority = async (index1, index2) => {
    if (index1 < 0 || index2 >= connections.length) return
    const newConns = [...connections]
    ;[newConns[index1], newConns[index2]] = [newConns[index2], newConns[index1]]
    setConnections(newConns)
    try {
      await Promise.all([
        providersApi.updateProvider(newConns[index1].id, { priority: index1 }),
        providersApi.updateProvider(newConns[index2].id, { priority: index2 }),
      ])
    } catch (err) {
      console.error('Failed to swap priority:', err)
      await fetchConnections()
    }
  }

  const handleDelete = (id) => {
    setConfirmState({
      title: 'Delete Connection',
      message: 'Delete this connection? This action cannot be undone.',
      onConfirm: async () => {
        setConfirmState(null)
        try {
          await providersApi.deleteProvider(id)
          setConnections((prev) => prev.filter((c) => c.id !== id))
        } catch (err) {
          console.error('Failed to delete:', err)
        }
      }
    })
  }

  const handleTestConnectionRow = async (connectionId) => {
    setTestingConnectionId(connectionId)
    setTestResults(prev => ({ ...prev, [connectionId]: null }))
    try {
      const res = await providersApi.testProvider(connectionId)
      const data = res.data
      setTestResults(prev => ({ ...prev, [connectionId]: { valid: data.valid, error: data.error } }))
      setConnections(prev => prev.map(c =>
        c.id === connectionId ? { ...c, test_status: data.valid ? 'connected' : 'error', last_error: data.error || null } : c
      ))
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Test failed'
      setTestResults(prev => ({ ...prev, [connectionId]: { valid: false, error: msg } }))
    } finally {
      setTestingConnectionId(null)
    }
  }

  // ── Compatible node handlers ──
  const handleUpdateNode = async (formData) => {
    try {
      await providersApi.updateProviderNode(providerId, formData)
      await fetchConnections()
      setShowEditNodeModal(false)
    } catch (error) {
      console.log('Error updating provider node:', error)
    }
  }

  const handleDeleteNode = () => {
    setConfirmState({
      title: 'Delete Compatible Node',
      message: `Delete this ${isAnthropicCompatible ? 'Anthropic' : 'OpenAI'} Compatible node? This will remove the provider.`,
      onConfirm: async () => {
        setConfirmState(null)
        try {
          await providersApi.deleteProviderNode(providerId)
          navigate('/providers')
        } catch (error) {
          console.log('Error deleting provider node:', error)
        }
      }
    })
  }

  // ── Bulk proxy ──
  const selectedConnections = connections.filter((conn) => selectedConnectionIds.includes(conn.id))
  const allSelected = connections.length > 0 && selectedConnectionIds.length === connections.length
  const allServiceKinds = [...new Set(connections.flatMap(c => c.serviceKinds || []))]

  const toggleSelectConnection = (connectionId) => {
    setSelectedConnectionIds((prev) =>
      prev.includes(connectionId) ? prev.filter((id) => id !== connectionId) : [...prev, connectionId]
    )
  }

  const toggleSelectAllConnections = () => {
    if (allSelected) { setSelectedConnectionIds([]); return }
    setSelectedConnectionIds(connections.map((conn) => conn.id))
  }

  const openBulkProxyModal = () => {
    if (selectedConnections.length === 0) return
    const uniquePoolIds = [...new Set(selectedConnections.map((conn) => conn.proxy_pool_id || '__none__'))]
    setBulkProxyPoolId(uniquePoolIds.length === 1 ? uniquePoolIds[0] : '__none__')
    setShowBulkProxyModal(true)
  }

  const applyProxyAssignments = async (assignments) => {
    setBulkUpdatingProxy(true)
    try {
      let failed = 0
      for (const { connectionId, proxyPoolId } of assignments) {
        try {
          await providersApi.updateProvider(connectionId, { proxyPoolId: proxyPoolId })
        } catch { failed += 1 }
      }
      if (failed > 0) alert(`Updated with ${failed} failed request(s).`)
      await fetchConnections()
      setShowBulkProxyModal(false)
    } finally {
      setBulkUpdatingProxy(false)
    }
  }

  const handleApplySinglePool = (proxyPoolId) => {
    const targets = connections.map((c) => ({ connectionId: c.id, proxyPoolId }))
    return applyProxyAssignments(targets)
  }

  const handleApplyOneToOne = () => {
    const activePools = proxyPools.filter((p) => p.is_active === true)
    if (activePools.length === 0) { alert('No active proxy pools available.'); return }
    const targets = connections.map((c, i) => ({
      connectionId: c.id,
      proxyPoolId: activePools[i % activePools.length].id,
    }))
    return applyProxyAssignments(targets)
  }

  // ── Effects ──
  useEffect(() => {
    fetchConnections()
    fetchAliases()
    fetchDisabledModels()
  }, [fetchConnections, fetchAliases, fetchDisabledModels])

  // Fetch suggested models from provider's public API (if configured)
  useEffect(() => {
    const fetcher = info?.modelsFetcher
    if (!fetcher) return
    fetchSuggestedModels(fetcher).then(setSuggestedModels)
  }, [providerId, info])

  useEffect(() => {
    setSelectedConnectionIds((prev) => prev.filter((id) => connections.some((conn) => conn.id === id)))
  }, [connections])

  // ── Render models section ──
  const renderModelsSection = () => {
    if (isCompatible) {
      return (
        <CompatibleModelsSection
          providerStorageAlias={providerStorageAlias}
          providerDisplayAlias={providerDisplayAlias}
          modelAliases={modelAliases}
          copied={copied}
          onCopy={handleCopy}
          onSetAlias={handleSetAlias}
          onDeleteAlias={handleDeleteAlias}
          connections={connections}
          isAnthropic={isAnthropicCompatible}
        />
      )
    }

    if (info?.passthroughModels) {
      return (
        <PassthroughModelsSection
          providerAlias={providerStorageAlias}
          modelAliases={modelAliases}
          copied={copied}
          onCopy={handleCopy}
          onSetAlias={handleSetAlias}
          onDeleteAlias={handleDeleteAlias}
          suggestedModels={suggestedModels}
        />
      )
    }

    const searchQ = modelSearchQuery.trim().toLowerCase()
    const disabledSet = new Set(disabledModelIds)

    // When enabledModelIds is empty (no connection-tracked models), treat ALL
    // non-disabled models as display models — matching the original Next.js
    // behavior where getModelsByProviderId() returned a flat display list.
    const hasEnabledTracking = enabledModelIds.size > 0

    // Display (active) models: non-disabled models from the known list.
    // When tracking is active, only models in enabledModelIds qualify.
    // When tracking is inactive, all non-disabled models qualify.
    const activeModels = models.filter((m) => {
      const mid = typeof m === 'string' ? m : m.id
      if (disabledSet.has(mid)) return false
      if (!hasEnabledTracking) return true
      return enabledModelIds.has(mid)
    })
    // Disabled models: in models list AND in disabledModelIds
    const disabledDisplayModels = models.filter((m) => disabledSet.has(typeof m === 'string' ? m : m.id))
    // Suggestion models: models NOT in active list (disabled + not-yet-enabled go to suggestions)
    const activeModelIds = new Set(activeModels.map(m => typeof m === 'string' ? m : m.id))
    const suggestionModels = models.filter((m) => {
      const mid = typeof m === 'string' ? m : m.id
      return !activeModelIds.has(mid)
    })
    // API-fetched suggested models from provider's public API (not already in the display list)
    const addedFullModels = new Set(Object.values(modelAliases))
    const knownModelIds = new Set(models.map((m) => typeof m === 'string' ? m : m.id))
    const apiSuggestedModels = (suggestedModels || []).filter((m) => {
      const mid = typeof m === 'string' ? m : m.id
      return !addedFullModels.has(`${providerStorageAlias}/${mid}`) && !knownModelIds.has(mid)
    })
    // Custom models added by user (stored as aliases)
    const customModels = Object.entries(modelAliases)
      .filter(([alias, fullModel]) => {
        const prefix = `${providerStorageAlias}/`
        if (!fullModel.startsWith(prefix)) return false
        const modelId = fullModel.slice(prefix.length)
        return !models.some((m) => (typeof m === 'string' ? m : m.id) === modelId) && alias === modelId
      })
      .map(([alias, fullModel]) => ({
        id: fullModel.slice(`${providerStorageAlias}/`.length),
        alias,
        fullModel,
      }))

    // Apply search filter to all lists
    const filteredCustom = searchQ
      ? customModels.filter((m) => m.id.toLowerCase().includes(searchQ) || m.fullModel.toLowerCase().includes(searchQ))
      : customModels
    const filteredActive = searchQ
      ? activeModels.filter((m) => (typeof m === 'string' ? m : m.id).toLowerCase().includes(searchQ))
      : activeModels
    const filteredDisabled = searchQ
      ? disabledDisplayModels.filter((m) => (typeof m === 'string' ? m : m.id).toLowerCase().includes(searchQ))
      : disabledDisplayModels
    const filteredSuggestions = searchQ
      ? suggestionModels.filter((m) => (typeof m === 'string' ? m : m.id).toLowerCase().includes(searchQ))
      : suggestionModels
    const filteredApiSuggestions = searchQ
      ? apiSuggestedModels.filter((m) => (typeof m === 'string' ? m : m.id).toLowerCase().includes(searchQ))
      : apiSuggestedModels
    return (
      <div className="flex flex-wrap gap-3">
        {/* Active (enabled) models */}
        {filteredActive.map((model) => {
          const modelId = typeof model === 'string' ? model : model.id
          const fullModelStr = `${providerDisplayAlias}/${modelId}`
          const oldFormatModel = `${providerId}/${modelId}`
          const existingAlias = Object.entries(modelAliases).find(
            ([, m]) => m === `${providerStorageAlias}/${modelId}` || m === oldFormatModel
          )?.[0]
          return (
            <ModelRow
              key={modelId}
              model={typeof model === 'string' ? { id: model } : model}
              fullModel={fullModelStr}
              alias={existingAlias}
              copied={copied}
              onCopy={handleCopy}
              onSetAlias={(alias) => handleSetAlias(modelId, alias)}
              onDeleteAlias={() => handleDeleteAlias(existingAlias)}
              testStatus={modelTestResults[modelId]}
              onTest={connections.length > 0 || isFreeNoAuth ? () => handleTestModel(modelId) : undefined}
              isTesting={testingModelId === modelId}
              onDisable={() => handleDisableModel(modelId)}
              modelType={getModelType(modelId)}
              onTypeChange={connections.length > 0 ? (newType) => handleChangeModelType(modelId, newType) : undefined}
            />
          )
        })}

        {/* Custom models (enabled, shown with active models above search) */}
        {filteredCustom.map((model) => (
          <ModelRow
            key={model.id}
            model={{ id: model.id }}
            fullModel={`${providerDisplayAlias}/${model.id}`}
            alias={model.alias}
            copied={copied}
            onCopy={handleCopy}
            onSetAlias={() => {}}
            onDeleteAlias={() => handleDeleteAlias(model.alias)}
            testStatus={modelTestResults[model.id]}
            onTest={connections.length > 0 || isFreeNoAuth ? () => handleTestModel(model.id) : undefined}
            isTesting={testingModelId === model.id}
            isCustom
            modelType={getModelType(model.id)}
            onTypeChange={connections.length > 0 ? (newType) => handleChangeModelType(model.id, newType) : undefined}
          />
        ))}

        {/* Search input - applies to all lists */}
        {(models.length > 0) && (
          <div className="w-full">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                value={modelSearchQuery}
                onChange={(e) => setModelSearchQuery(e.target.value)}
                placeholder="Search models..."
                className="w-full pl-8 pr-8 py-1.5 text-xs rounded-lg border border-zinc-700 bg-zinc-900/50 text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-primary-500/50"
              />
              {modelSearchQuery && (
                <button
                  type="button"
                  onClick={() => setModelSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Add model button */}
        <button
          onClick={() => setShowAddCustomModel(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-primary-500/40 px-3 py-2 text-xs text-primary-400 transition-colors hover:border-primary-500 hover:bg-primary-500/5 sm:w-auto"
        >
          <Plus size={14} /> Add Model
        </button>

        {/* Fetched but not yet enabled models (suggestions) — includes disabled models */}
        {filteredSuggestions.length > 0 && (
          <div className="w-full mt-2">
            <p className="text-xs text-zinc-500 mb-2">Available to enable ({suggestionModels.length}):</p>
            <div className="flex flex-wrap gap-1.5">
              {filteredSuggestions.map((m) => {
                const modelId = typeof m === 'string' ? m : m.id
                const isDisabled = disabledSet.has(modelId)
                return (
                  <button
                    key={modelId}
                    onClick={() => isDisabled ? handleEnableModel(modelId) : addModel(modelId)}
                    className="inline-flex items-center gap-1 rounded-md border border-dashed border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:border-primary-500/50 hover:text-primary-400 hover:bg-primary-900/10 transition-colors"
                  >
                    <Plus size={10} /> {modelId}
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* API-fetched suggested models from provider's public API */}
        {filteredApiSuggestions.length > 0 && (
          <div className="w-full mt-2">
            <p className="text-xs text-zinc-500 mb-2">Suggested models ({filteredApiSuggestions.length}):</p>
            <div className="flex flex-wrap gap-1.5">
              {filteredApiSuggestions.map((m) => {
                const modelId = typeof m === 'string' ? m : m.id
                const modelObj = typeof m === 'object' ? m : null
                return (
                  <button
                    key={modelId}
                    onClick={() => addModel(modelId)}
                    className="inline-flex items-center gap-1 rounded-md border border-dashed border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:border-primary-500/50 hover:text-primary-400 hover:bg-primary-900/10 transition-colors"
                    title={modelObj?.name ? `${modelObj.name}${modelObj.contextLength ? ` · ${(modelObj.contextLength / 1000).toFixed(0)}k ctx` : ''}` : undefined}
                  >
                    <Plus size={10} /> {modelId}
                  </button>
                )
              })}
            </div>
          </div>
        )}

      </div>
    )
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  // ── Not found (standard provider) ──
  if (!info && !providerNode) {
    return (
      <div className="text-center py-20">
        <p className="text-zinc-400">Provider not found</p>
        <Link to="/providers" className="text-primary-400 hover:underline text-sm mt-2 inline-block">
          Back to Providers
        </Link>
      </div>
    )
  }

  const activePools = proxyPools.filter((p) => p.is_active === true)

  return (
    <div className="flex min-w-0 flex-col gap-6 px-1 sm:gap-8 sm:px-0">
      {/* ── Header ── */}
      <div className="min-w-0">
        <Link
          to="/providers"
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-primary-400 transition-colors mb-4"
        >
          <ArrowLeft size={16} /> Back to Providers
        </Link>
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          {headerImgError ? (
            <div
              className="flex size-12 shrink-0 items-center justify-center rounded-lg text-base font-bold"
              style={{ backgroundColor: `${displayInfo.color}15`, color: displayInfo.color }}
            >
              {displayInfo.icon}
            </div>
          ) : (
            <img
              src={`/providers/${providerId}.png`}
              alt={displayInfo.name}
              width={48}
              height={48}
              className="size-12 shrink-0 rounded-lg object-contain"
              onError={() => setHeaderImgError(true)}
            />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="truncate text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">{displayInfo.name}</h1>
              {info?.apiKeyUrl && (
                <a href={info.apiKeyUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-primary-400 hover:underline inline-flex items-center gap-1">
                  <ExternalLink size={12} /> Get API Key
                </a>
              )}
              {allServiceKinds.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {allServiceKinds.map(kind => (
                    <span key={kind} className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${TYPE_BADGE_STYLES[kind] || TYPE_BADGE_STYLES.llm}`}>
                      {kind}
                    </span>
                  ))}
                </div>
              )}
            </div>
            <p className="text-zinc-500">
              {connections.length} connection{connections.length === 1 ? '' : 's'} configured
            </p>
          </div>
        </div>
      </div>

      {/* ── Compatible provider node info ── */}
      {isCompatible && providerNode && (
        <Card>
          <CardContent>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="text-lg font-semibold text-zinc-100">{isAnthropicCompatible ? 'Anthropic Compatible Details' : 'OpenAI Compatible Details'}</h2>
                <p className="break-all text-sm text-zinc-400">
                  {isAnthropicCompatible ? 'Messages API' : (providerNode.api_type === 'responses' ? 'Responses API' : 'Chat Completions')} · {(providerNode.base_url || '').replace(/\/$/, '')}/
                  {isAnthropicCompatible ? 'messages' : (providerNode.api_type === 'responses' ? 'responses' : 'chat/completions')}
                </p>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:flex sm:items-center">
                <Button size="sm" onClick={() => { setAddConnectionError(''); setShowAddModal(true) }} className="w-full sm:w-auto">
                  <Plus size={14} /> Add API Key
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setShowEditNodeModal(true)} className="w-full sm:w-auto">
                  <Edit2 size={14} /> Edit
                </Button>
                <Button size="sm" variant="danger" onClick={handleDeleteNode} className="w-full sm:w-auto">
                  <Trash2 size={14} /> Delete
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Connections Card ── */}
      <Card>
        <CardContent>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-zinc-100">Connections</h2>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
              {/* Bulk proxy button */}
              {connections.length > 0 && proxyPools.length > 0 && (
                <Button size="sm" variant="secondary" onClick={() => setShowBulkProxyModal(true)}>
                  <Network size={14} /> Apply Proxy
                </Button>
              )}
              {/* Strategy selector */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-zinc-400 font-medium">Strategy</span>
                <select
                  value={providerStrategy || 'fill-first'}
                  onChange={(e) => handleStrategyChange(e.target.value)}
                  className="px-2 py-1 text-xs border border-zinc-700 rounded-md bg-zinc-800/50 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                  <option value="fill-first">Fill First</option>
                  <option value="round-robin">Round Robin</option>
                  <option value="random">Random</option>
                </select>
                {providerStrategy === 'round-robin' && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-zinc-400">Sticky:</span>
                    <input
                      type="number"
                      min={1}
                      value={providerStickyLimit}
                      onChange={(e) => handleStickyLimitChange(e.target.value)}
                      placeholder="1"
                      className="w-14 px-2 py-1 text-xs border border-zinc-700 rounded-md bg-zinc-800/50 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                  </div>
                )}
              </div>
              {/* Thinking Mode selector */}
              {thinkingConfig.options && thinkingConfig.options.length > 1 && (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-zinc-400 font-medium">Thinking</span>
                  <select
                    value={thinkingMode}
                    onChange={(e) => handleThinkingModeChange(e.target.value)}
                    className="px-2 py-1 text-xs border border-zinc-700 rounded-md bg-zinc-800/50 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500"
                  >
                    {thinkingConfig.options.map(mode => (
                      <option key={mode} value={mode}>
                        {mode.charAt(0).toUpperCase() + mode.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          {connections.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary-600/10 text-primary-400 mb-4">
                {isOAuth ? <Lock size={20} /> : <Key size={20} />}
              </div>
              <p className="text-sm text-zinc-400 mb-4">No connections yet</p>
              {isFreeNoAuth ? (
                <Button size="sm" onClick={handleNoAuthConnect} disabled={connectingNoAuth}>
                  {connectingNoAuth ? (
                    <><Loader2 size={14} className="animate-spin mr-1" /> Connecting...</>
                  ) : (
                    <><Plug size={14} className="mr-1" /> Connect</>
                  )}
                </Button>
              ) : (
                <Button size="sm" onClick={() => {
                  if (isOAuth) {
                    setShowOAuthModal(true)
                  } else {
                    setAddConnectionError(''); setShowAddModal(true)
                  }
                }}>
                  <Plus size={14} /> {isCompatible ? 'Add API Key' : 'Add Connection'}
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="flex min-w-0 flex-col divide-y divide-zinc-800/50">
                {connections.map((conn, index) => (
                  <div key={conn.id} className="flex min-w-0 items-stretch">
                    <div className="flex-1 min-w-0">
                      <ConnectionRow
                        connection={conn}
                        proxyPools={proxyPools}
                        isFirst={index === 0}
                        isLast={index === connections.length - 1}
                        isOAuth={isOAuth}
                        onMoveUp={() => handleSwapPriority(index, index - 1)}
                        onMoveDown={() => handleSwapPriority(index, index + 1)}
                        onToggleActive={(isActive) => handleToggleActive(conn.id, isActive)}
                        onUpdateProxy={async (proxyPoolId) => {
                          try {
                            await providersApi.updateProvider(conn.id, { proxyPoolId: proxyPoolId || null })
                            setConnections(prev => prev.map(c =>
                              c.id === conn.id ? { ...c, proxy_pool_id: proxyPoolId || null } : c
                            ))
                          } catch (error) {
                            console.error('Error updating proxy:', error)
                          }
                        }}
                        onEdit={() => { setSelectedConnection(conn); setShowEditModal(true) }}
                        onDelete={() => handleDelete(conn.id)}
                        onTest={() => handleTestConnectionRow(conn.id)}
                        testing={testingConnectionId === conn.id}
                        testResult={testResults[conn.id]}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex justify-stretch sm:justify-start">
                <Button size="sm" onClick={() => {
                  if (isOAuth) {
                    setShowOAuthModal(true)
                  } else {
                    setAddConnectionError(''); setShowAddModal(true)
                  }
                }}>
                  <Plus size={14} /> Add
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* ── Models Card ── */}
      <Card>
        <CardContent>
          <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-zinc-100">Available Models</h2>
            {!isCompatible && models.length > 0 && (() => {
              const disabledSet = new Set(disabledModelIds)
              const activeIds = models.filter((m) => !disabledSet.has(typeof m === 'string' ? m : m.id))
              return (
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" onClick={handleFetchModels} disabled={fetchingModels || !connections.length}>
                    {fetchingModels ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                    {fetchingModels ? 'Fetching...' : 'Fetch Models'}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={handleClearModels} disabled={clearingModels}>
                    {clearingModels ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                    {clearingModels ? 'Clearing...' : 'Clear Models'}
                  </Button>
                  {disabledModelIds.length > 0 && (
                    <Button size="sm" variant="secondary" onClick={handleEnableAll}>
                      <RotateCcw size={14} /> Enable All
                    </Button>
                  )}
                  {activeIds.length > 0 && (
                    <Button size="sm" variant="secondary" onClick={() => handleDisableAll(activeIds.map(m => typeof m === 'string' ? m : m.id))}>
                      <Ban size={14} /> Disable All
                    </Button>
                  )}
                </div>
              )
            })()}
            {!isCompatible && models.length === 0 && connections.length > 0 && (
              <Button size="sm" variant="secondary" onClick={handleFetchModels} disabled={fetchingModels}>
                {fetchingModels ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                {fetchingModels ? 'Fetching...' : 'Fetch Models'}
              </Button>
            )}
          </div>
          {!!modelsTestError && (
            <p className="text-xs text-red-500 mb-3 break-words">{modelsTestError}</p>
          )}
          {renderModelsSection()}
        </CardContent>
      </Card>

      {/* ── Chat Test Playground ── */}
      <ChatTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />

      {/* ── Bulk Proxy Modal ── */}
      <Modal
        isOpen={showBulkProxyModal}
        onClose={() => { if (!bulkUpdatingProxy) setShowBulkProxyModal(false) }}
        title={`Apply Proxy (${connections.length} connections)`}
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-col">
            <button
              onClick={handleApplyOneToOne}
              disabled={bulkUpdatingProxy || activePools.length === 0}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="text-zinc-500"><Network size={16} /></span>
              <span className="text-sm text-zinc-200">One-to-one (rotate)</span>
            </button>
            <button
              onClick={() => handleApplySinglePool(null)}
              disabled={bulkUpdatingProxy}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="text-zinc-500"><X size={16} /></span>
              <span className="text-sm text-zinc-200">None (unbind all)</span>
            </button>
            {proxyPools.map((pool) => (
              <button
                key={pool.id}
                onClick={() => handleApplySinglePool(pool.id)}
                disabled={bulkUpdatingProxy || pool.is_active !== true}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-left transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="text-zinc-500"><Network size={16} /></span>
                <span className="truncate text-sm text-zinc-200">{pool.name}</span>
                {pool.is_active !== true && <span className="text-[10px] text-zinc-500">(inactive)</span>}
              </button>
            ))}
          </div>
          {bulkUpdatingProxy && <p className="text-xs text-zinc-500">Applying...</p>}
          <Button onClick={() => setShowBulkProxyModal(false)} variant="ghost" className="w-full" disabled={bulkUpdatingProxy}>
            Cancel
          </Button>
        </div>
      </Modal>

      {/* ── Add Key Modal ── */}
      <AddKeyModal
        isOpen={showAddModal}
        providerId={providerId}
        info={isCompatible ? { name: displayInfo.name } : info}
        isCompatible={isCompatible}
        isAnthropicCompatible={isAnthropicCompatible}
        proxyPools={proxyPools}
        onCreated={async () => {
          setShowAddModal(false)
          setAddConnectionError('')
          await fetchConnections()
        }}
        onClose={() => { setAddConnectionError(''); setShowAddModal(false) }}
      />

      {/* ── Edit Connection Modal ── */}
      {selectedConnection && (
        isConnectionOAuth(selectedConnection, providerId) ? (
          <OAuthEditModal
            isOpen={showEditModal}
            connection={selectedConnection}
            proxyPools={proxyPools}
            onClose={() => { setShowEditModal(false); setSelectedConnection(null) }}
            onSave={async () => { setShowEditModal(false); setSelectedConnection(null); await fetchConnections() }}
          />
        ) : (
          <AddKeyModal
            isOpen={showEditModal}
            providerId={providerId}
            info={isCompatible ? { name: displayInfo.name } : info}
            isCompatible={isCompatible}
            isAnthropicCompatible={isAnthropicCompatible}
            editConnection={selectedConnection}
            proxyPools={proxyPools}
            onClose={() => { setShowEditModal(false); setSelectedConnection(null) }}
            onCreated={async () => { setShowEditModal(false); setSelectedConnection(null); await fetchConnections() }}
          />
        )
      )}

      {/* ── Edit Compatible Node Modal ── */}
      {isCompatible && (
        <EditCompatibleNodeModal
          isOpen={showEditNodeModal}
          node={providerNode}
          onSave={handleUpdateNode}
          onClose={() => setShowEditNodeModal(false)}
          isAnthropic={isAnthropicCompatible}
        />
      )}

      {/* ── Add Custom Model Modal ── */}
      <AddCustomModelModal
        isOpen={showAddCustomModel}
        providerAlias={providerStorageAlias}
        providerDisplayAlias={providerDisplayAlias}
        onSave={async (modelId) => {
          await handleSetAlias(modelId, modelId)
          setShowAddCustomModel(false)
        }}
        onClose={() => setShowAddCustomModel(false)}
      />

      {/* ── OAuth / Provider-specific Modal ── */}
      {(() => {
        const customModal = info?.customModal
        const handleClose = () => setShowOAuthModal(false)
        const handleSuccess = () => { setShowOAuthModal(false); fetchConnections() }

        if (customModal === 'kiro') {
          return <KiroAuthModal isOpen={showOAuthModal} onClose={handleClose} onMethodSelect={handleSuccess} />
        }
        if (customModal === 'cursor') {
          return <CursorAuthModal isOpen={showOAuthModal} onSuccess={handleSuccess} onClose={handleClose} />
        }
        if (customModal === 'gitlab') {
          return <GitLabAuthModal isOpen={showOAuthModal} providerInfo={info} onSuccess={handleSuccess} onClose={handleClose} />
        }
        return <OAuthModal isOpen={showOAuthModal} provider={providerId} providerInfo={info} onSuccess={handleSuccess} onClose={handleClose} />
      })()}

      {/* ── Confirm Modal ── */}
      <ConfirmModal
        isOpen={!!confirmState}
        onClose={() => setConfirmState(null)}
        onConfirm={confirmState?.onConfirm}
        title={confirmState?.title || 'Confirm'}
        message={confirmState?.message}
        variant="danger"
      />
    </div>
  )
}
