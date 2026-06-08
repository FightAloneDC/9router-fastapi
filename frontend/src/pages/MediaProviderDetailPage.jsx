import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft, Plus, Trash2, Key, Eye, EyeOff,
  ChevronUp, ChevronDown, CheckCircle2, AlertCircle,
  Loader2, Wifi, Edit2, ExternalLink, X, Copy, Check,
  Download, Network, RotateCcw, Search, Info, Plug, Play,
  Beaker, Ban, Volume2, Mic, Upload, FileAudio, ImageIcon,
} from 'lucide-react'
import Card, { CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import { providersApi } from '../api/providers'
import { proxyPoolsApi } from '../api/proxyPools'
import { settingsApi } from '../api/settings'
import useCatalogStore from '../stores/catalogStore'
import { useAuthStore } from '../stores/authStore'
import { copyToClipboard } from '../utils/clipboard'


/* ════════════════════════════════════════════════════════════════
   TYPE_BADGE_STYLES — colored badges for service kinds
   ════════════════════════════════════════════════════════════════ */
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
   CooldownTimer
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
   ConfirmModal
   ════════════════════════════════════════════════════════════════ */
function ConfirmModal({ isOpen, onClose, onConfirm, title, message }) {
  if (!isOpen) return null
  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title || 'Confirm'}>
      <p className="text-sm text-zinc-300 mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="danger" onClick={onConfirm}>Delete</Button>
      </div>
    </Modal>
  )
}


/* ════════════════════════════════════════════════════════════════
   ConnectionRow
   ════════════════════════════════════════════════════════════════ */
function ConnectionRow({ connection, proxyPools, isFirst, isLast, onMoveUp, onMoveDown, onToggleActive, onUpdateProxy, onEdit, onDelete, onTest, testing, testResult }) {
  const isActive = connection.is_active ?? true
  const status = connection.test_status || 'untested'

  const providerSpecific = connection.provider_specific || {}
  const modelLockUntil = Object.entries(providerSpecific)
    .filter(([k]) => k.startsWith('modelLock_'))
    .map(([, v]) => v).filter(Boolean).sort()[0] || null
  const isCooldown = modelLockUntil && new Date(modelLockUntil).getTime() > Date.now()

  const boundProxyPoolId = connection.proxy_pool_id || null
  const proxyPoolMap = new Map((proxyPools || []).map((p) => [p.id, p]))
  const boundProxyPool = boundProxyPoolId ? proxyPoolMap.get(boundProxyPoolId) : null
  const proxyDisplayText = boundProxyPool
    ? `Pool: ${boundProxyPool.name}`
    : boundProxyPoolId ? `Pool: ${boundProxyPoolId} (missing)` : ''

  const effectiveStatus = isCooldown && isActive ? 'active' : status

  const getStatusVariant = () => {
    if (!isActive) return 'default'
    if (['connected', 'active', 'success'].includes(effectiveStatus)) return 'success'
    if (['error', 'expired', 'unavailable'].includes(effectiveStatus)) return 'danger'
    if (effectiveStatus === 'untested') return 'warning'
    return 'default'
  }

  return (
    <div className={`group flex flex-col gap-3 p-2 rounded-lg sm:flex-row sm:items-center sm:justify-between hover:bg-zinc-800/40 transition-colors ${!isActive ? 'opacity-60' : ''}`}>
      <div className="flex w-full min-w-0 flex-1 items-start gap-3 sm:items-center">
        <div className="flex shrink-0 flex-col">
          <button onClick={onMoveUp} disabled={isFirst} className={`p-0.5 rounded ${isFirst ? 'text-zinc-700 cursor-not-allowed' : 'text-zinc-500 hover:text-primary-400 hover:bg-zinc-800'}`}>
            <ChevronUp size={14} />
          </button>
          <button onClick={onMoveDown} disabled={isLast} className={`p-0.5 rounded ${isLast ? 'text-zinc-700 cursor-not-allowed' : 'text-zinc-500 hover:text-primary-400 hover:bg-zinc-800'}`}>
            <ChevronDown size={14} />
          </button>
        </div>

        <Key size={16} className="shrink-0 text-zinc-500" />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-zinc-200 truncate">
            {connection.name || connection.email || 'Unnamed Connection'}
          </p>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-1.5">
            <Badge variant={getStatusVariant()} size="sm" dot>
              {!isActive ? 'disabled' : (effectiveStatus || 'untested')}
            </Badge>
            {boundProxyPoolId && <Badge variant="info" size="sm">Proxy</Badge>}
            {isCooldown && isActive && <CooldownTimer until={modelLockUntil} />}
            {connection.priority != null && (
              <span className="text-xs text-zinc-500">#{connection.priority}</span>
            )}
          </div>
          {boundProxyPoolId && (
            <span className="text-[11px] text-zinc-500 truncate max-w-[420px] block mt-1" title={proxyDisplayText}>{proxyDisplayText}</span>
          )}
          {connection.last_error && isActive && (
            <span className="text-xs text-red-500 truncate max-w-[300px] block" title={connection.last_error}>{connection.last_error}</span>
          )}
        </div>
      </div>

      <div className="flex w-full flex-wrap items-center justify-between gap-2 sm:w-auto sm:justify-end">
        <div className="flex flex-wrap gap-1">
          {(proxyPools || []).length > 0 && (
            <ProxySelector
              connection={connection}
              proxyPools={proxyPools}
              onUpdateProxy={onUpdateProxy}
            />
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
   ProxySelector — dropdown for binding connection to a proxy pool
   ════════════════════════════════════════════════════════════════ */
function ProxySelector({ connection, proxyPools, onUpdateProxy }) {
  const [showDropdown, setShowDropdown] = useState(false)
  const [updating, setUpdating] = useState(false)
  const ref = { current: null }

  const boundId = connection.proxy_pool_id || null

  useEffect(() => {
    if (!showDropdown) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setShowDropdown(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showDropdown])

  const handleSelect = async (poolId) => {
    setUpdating(true)
    try { await onUpdateProxy(poolId === '__none__' ? null : poolId) }
    finally { setUpdating(false); setShowDropdown(false) }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setShowDropdown(v => !v)}
        className={`flex flex-col items-center px-2 py-1 rounded hover:bg-zinc-800 transition-colors ${boundId ? 'text-primary-400' : 'text-zinc-500 hover:text-primary-400'}`}
        disabled={updating}
      >
        <Network size={16} />
        <span className="text-[10px] leading-tight">Proxy</span>
      </button>
      {showDropdown && (
        <div className="absolute right-0 top-full mt-1 z-50 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg py-1 min-w-[160px]">
          <button onClick={() => handleSelect('__none__')} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-zinc-700 ${!boundId ? 'text-primary-400 font-medium' : 'text-zinc-300'}`}>None</button>
          {(proxyPools || []).map((pool) => (
            <button key={pool.id} onClick={() => handleSelect(pool.id)} className={`w-full text-left px-3 py-1.5 text-sm hover:bg-zinc-700 ${boundId === pool.id ? 'text-primary-400 font-medium' : 'text-zinc-300'}`}>{pool.name}</button>
          ))}
        </div>
      )}
    </div>
  )
}


/* ════════════════════════════════════════════════════════════════
   AddKeyModal — synced with ProviderDetailPage.jsx (LLM reference)
   ════════════════════════════════════════════════════════════════ */
function AddKeyModal({ isOpen, providerId, provider, editConnection, onClose, onCreated, proxyPools = [], isCompatible = false }) {
  const isEdit = !!editConnection
  const isNoAuth = provider?.noAuth === true

  const [name, setName] = useState('')
  const [priority, setPriority] = useState(0)
  const [proxyPoolId, setProxyPoolId] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
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
      } else {
        setName('')
        setPriority(0)
        setProxyPoolId('')
        setApiKey('')
        setBaseUrl('')
        setDefaultModel('')
      }
      setValidationResult(null)
      setSkipValidation(false)
      setShowApiKey(false)
      setError('')
    }
  }, [isOpen, providerId, editConnection])

  const handleValidate = async () => {
    setValidating(true)
    setValidationResult(null)
    try {
      const res = await providersApi.validateProvider({
        provider: providerId,
        apiKey: apiKey.trim(),
        baseUrl: baseUrl.trim() || undefined,
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
    if (!isNoAuth && !isEdit && !apiKey.trim()) return
    if (!isNoAuth && !isEdit && !name.trim()) return
    if (isCompatible && !defaultModel.trim()) return

    setCreating(true)
    setError('')
    try {
      if (isEdit) {
        const updateData = {
          name: name.trim() || editConnection.name,
          baseUrl: baseUrl.trim() || undefined,
          priority,
          proxyPoolId: proxyPoolId || null,
          defaultModel: isCompatible ? defaultModel.trim() : undefined,
        }
        if (apiKey.trim()) updateData.apiKey = apiKey.trim()
        await providersApi.updateProvider(editConnection.id, updateData)
      } else {
        await providersApi.createProvider({
          provider: providerId,
          apiKey: isNoAuth ? '' : apiKey.trim(),
          auth_type: isNoAuth ? 'free' : 'apikey',
          noAuth: isNoAuth,
          name: name.trim() || null,
          baseUrl: baseUrl.trim() || undefined,
          priority,
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
    || (!isNoAuth && !isEdit && (!name.trim() || !apiKey.trim()))
    || (isCompatible && !defaultModel.trim())

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isEdit ? `Edit ${provider?.name || ''} Connection` : `Add ${provider?.name || ''} API Key`}
      className="max-w-xl"
    >
      <div className="space-y-4">
        <Input
          label="Name *"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Production Key"
          hint={!isNoAuth && !isEdit ? 'Required — e.g. Production, Personal, Team' : undefined}
        />

        {!isNoAuth && (
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Input
                label="API Key"
                type={showApiKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={isEdit ? '(leave empty to keep current)' : 'sk-...'}
              />
              <button
                type="button"
                onClick={() => setShowApiKey((v) => !v)}
                className="absolute right-3 top-[34px] text-zinc-500 hover:text-zinc-300"
              >
                {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <div className="pt-6 shrink-0">
              <Button onClick={handleValidate} disabled={!apiKey.trim() || validating || creating} variant="secondary">
                {validating ? 'Checking...' : 'Check'}
              </Button>
            </div>
          </div>
        )}

        {isNoAuth && (
          <p className="text-xs text-zinc-400 bg-zinc-900/50 p-3 rounded-lg border border-zinc-700/40">
            This provider does not require an API key. Just give the connection a name and save.
          </p>
        )}

        {isCompatible && (
          <Input
            label="Default Model"
            value={defaultModel}
            onChange={(e) => setDefaultModel(e.target.value)}
            placeholder="model-id"
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
              {(proxyPools || []).map((pool) => (
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
            disabled={validating || (isNoAuth ? true : !apiKey.trim())}
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
   AddCustomModelModal — test-before-add modal (copy from LLM reference)
   ════════════════════════════════════════════════════════════════ */
function AddCustomModelModal({ isOpen, providerAlias, onSave, onClose }) {
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
              placeholder="e.g. en-US-AriaNeural"
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
   ModelRow — single model chip with copy, test, disable, type dropdown
   ════════════════════════════════════════════════════════════════ */
function ModelRow({ model, fullModel, copied, onCopy, testStatus, onTest, isTesting, onDisable, modelType, onTypeChange }) {
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
          <p className="text-xs font-medium text-zinc-200 truncate">{model.id || model}</p>
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
          {!onTypeChange && modelType && (
            <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${TYPE_BADGE_STYLES[modelType] || TYPE_BADGE_STYLES.llm}`}>{modelType}</span>
          )}
        </div>
        <div className="flex items-center gap-1 mt-0.5">
          <code className="text-[10px] text-zinc-500 font-mono bg-zinc-800 px-1 py-0.5 rounded truncate max-w-[180px]">{fullModel}</code>
          <button onClick={() => onCopy(fullModel, `model-${model.id || model}`)} className="p-0.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-primary-400">
            {copied === `model-${model.id || model}` ? <Check size={12} /> : <Copy size={12} />}
          </button>
        </div>
      </div>

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
    </div>
  )
}


/* ════════════════════════════════════════════════════════════════
   EmbeddingTestPlayground — real API test for embedding providers
   ════════════════════════════════════════════════════════════════ */
function EmbeddingTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [selectedModel, setSelectedModel] = useState('')
  const [input, setInput] = useState('The quick brown fox jumps over the lazy dog')
  const [dimensions, setDimensions] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [copiedRes, setCopiedRes] = useState(false)
  const [availableModels, setAvailableModels] = useState([])

  useEffect(() => {
    fetch(`/v1/models?kind=embedding`, {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.json())
      .then(data => {
        const allModels = data.data || []
        const filtered = allModels.filter(m => {
          const id = m.id || ''
          return id.startsWith(`${providerAlias}/`) || id.startsWith(`${providerId}/`)
        })
        setAvailableModels(filtered)
        if (filtered.length > 0 && !selectedModel) setSelectedModel(filtered[0].id)
      })
      .catch(() => {})
  }, [providerId, providerAlias, token])

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
            {availableModels.length === 0 && <p className="text-[10px] text-zinc-600 mt-1">No models fetched. Type model ID manually.</p>}
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Input Text</label>
            <input value={input} onChange={e => setInput(e.target.value)} placeholder="The quick brown fox..."
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-primary-500" />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Dimensions <span className="text-zinc-600">(optional)</span></label>
            <input type="number" min="1" value={dimensions} onChange={e => setDimensions(e.target.value)} placeholder="e.g. 512, 1024"
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
   TtsTestPlayground — Voice synthesis playground for /v1/audio/speech
   ════════════════════════════════════════════════════════════════ */
function TtsTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [selectedModel, setSelectedModel] = useState('')
  const [voice, setVoice] = useState('')
  const [input, setInput] = useState('Hello, this is a text to speech test.')
  const [responseFormat, setResponseFormat] = useState('mp3') // mp3 | json
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [jsonResponse, setJsonResponse] = useState(null)
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [availableModels, setAvailableModels] = useState([])
  const [availableVoices, setAvailableVoices] = useState([])
  const [loadingVoices, setLoadingVoices] = useState(false)
  const audioUrlRef = useRef('')

  // Fetch TTS models for this provider
  useEffect(() => {
    fetch(`/v1/models?kind=tts`, {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.json())
      .then(data => {
        const allModels = data.data || []
        const filtered = allModels.filter(m => {
          const id = m.id || ''
          return id.startsWith(`${providerAlias}/`) || id.startsWith(`${providerId}/`)
        })
        setAvailableModels(filtered)
        if (filtered.length > 0 && !selectedModel) setSelectedModel(filtered[0].id)
      })
      .catch(() => {})
  }, [providerId, providerAlias, token])

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
            {availableModels.length === 0 && <p className="text-[10px] text-zinc-600 mt-1">No TTS models registered for this provider. Type model ID manually (e.g. {providerAlias}/voice-name).</p>}
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
function SttTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [selectedModel, setSelectedModel] = useState('')
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
  const [availableModels, setAvailableModels] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const fileInputRef = useRef(null)

  // Fetch STT models for this provider
  useEffect(() => {
    fetch(`/v1/models?kind=stt`, {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.json())
      .then(data => {
        const allModels = data.data || []
        const filtered = allModels.filter(m => {
          const id = m.id || ''
          return id.startsWith(`${providerAlias}/`) || id.startsWith(`${providerId}/`)
        })
        setAvailableModels(filtered)
        if (filtered.length > 0 && !selectedModel) setSelectedModel(filtered[0].id)
      })
      .catch(() => {})
  }, [providerId, providerAlias, token])

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
            {availableModels.length === 0 && <p className="text-[10px] text-zinc-600 mt-1">No STT models registered for this provider. Type model ID manually (e.g. {providerAlias}/whisper-1).</p>}
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
function ImageTestPlayground({ providerId, providerAlias, connections }) {
  const token = useAuthStore(s => s.token)
  const [selectedModel, setSelectedModel] = useState('')
  const [prompt, setPrompt] = useState('A beautiful sunset over the ocean, digital art')
  const [size, setSize] = useState('1024x1024')
  const [n, setN] = useState(1)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [latency, setLatency] = useState(null)
  const [copiedCurl, setCopiedCurl] = useState(false)
  const [availableModels, setAvailableModels] = useState([])

  useEffect(() => {
    fetch(`/v1/models?kind=image`, {
      headers: { 'Authorization': `Bearer ${token || ''}` },
    })
      .then(r => r.json())
      .then(data => {
        const allModels = data.data || []
        const filtered = allModels.filter(m => {
          const id = m.id || ''
          return id.startsWith(`${providerAlias}/`) || id.startsWith(`${providerId}/`)
        })
        setAvailableModels(filtered)
        if (filtered.length > 0 && !selectedModel) setSelectedModel(filtered[0].id)
      })
      .catch(() => {})
  }, [providerId, providerAlias, token])

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


/* ════════════════════════════════════════════════════════════════
   Main Page
   ════════════════════════════════════════════════════════════════ */
export default function MediaProviderDetailPage() {
  const { kind, providerId } = useParams()
  const navigate = useNavigate()
  const catalogStore = useCatalogStore()
  const provider = catalogStore.providers[providerId]
  const kindConfig = catalogStore.getKindConfig(kind)
  const providerAlias = provider ? catalogStore.getProviderAlias(providerId) : providerId
  const kinds = provider?.serviceKinds || ['llm']
  const allServiceKinds = provider?.serviceKinds || []

  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [proxyPools, setProxyPools] = useState([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedConnection, setSelectedConnection] = useState(null)
  const [confirmState, setConfirmState] = useState(null)
  const [testingConnectionId, setTestingConnectionId] = useState(null)
  const [testResults, setTestResults] = useState({})

  // Models state
  const [models, setModels] = useState([])
  const [disabledModelIds, setDisabledModelIds] = useState([])
  const [showAddCustomModel, setShowAddCustomModel] = useState(false)
  const [modelSearchQuery, setModelSearchQuery] = useState('')
  const [copied, setCopied] = useState(null)
  const [fetchingModels, setFetchingModels] = useState(false)
  const [clearingModels, setClearingModels] = useState(false)
  const [modelTestResults, setModelTestResults] = useState({})
  const [testingModelId, setTestingModelId] = useState(null)

  // Settings
  const [providerStrategy, setProviderStrategy] = useState(null)
  const [providerStickyLimit, setProviderStickyLimit] = useState('1')

  // Header image
  const [headerImgError, setHeaderImgError] = useState(false)

  const handleCopy = useCallback((text, id) => {
    copyToClipboard(text).then((ok) => {
      if (ok) { setCopied(id); setTimeout(() => setCopied(null), 2000) }
    })
  }, [])

  // Fetch connections + pools + settings
  const fetchConnections = useCallback(async () => {
    try {
      const [connRes, proxyRes] = await Promise.all([providersApi.getProviders(), proxyPoolsApi.getAll()])
      const allConns = connRes.data || []
      const filtered = allConns.filter((c) => c.provider === providerId)
      filtered.sort((a, b) => (a.priority ?? 0) - (b.priority ?? 0))
      setConnections(filtered)
      setProxyPools((proxyRes.data || []).filter((p) => p.is_active !== false))

      // Derive models from connections
      if (filtered.length > 0) {
        const allModels = new Set()
        filtered.forEach(c => (c.models || []).forEach(m => allModels.add(typeof m === 'string' ? m : m.id)))
        setModels([...allModels])
      } else {
        setModels([])
      }

      // Settings for strategy
      try {
        const settingsRes = await settingsApi.get()
        const settingsData = settingsRes.data || {}
        const strategies = settingsData.providerStrategies || settingsData.provider_strategies || {}
        const override = strategies[providerId] || {}
        setProviderStrategy(override.fallbackStrategy || override.fallback_strategy || null)
        const sticky = override.stickyRoundRobinLimit ?? override.sticky_round_robin_limit
        setProviderStickyLimit(sticky != null ? String(sticky) : '1')
      } catch {}
    } catch (err) {
      console.error('Failed to fetch connections:', err)
    } finally {
      setLoading(false)
    }
  }, [providerId])

  useEffect(() => { fetchConnections() }, [fetchConnections])

  // Fetch disabled models
  useEffect(() => {
    const fetchDisabled = async () => {
      try {
        const { default: client } = await import('../api/client')
        const res = await client.get('/models/disabled', { params: { providerAlias } })
        if (res.data?.ids) setDisabledModelIds(res.data.ids)
      } catch {}
    }
    fetchDisabled()
  }, [providerAlias])

  const providerConns = connections.filter((c) => c.provider === providerId)

  // ── Connection handlers ──
  const handleSwapPriority = (fromIndex, toIndex) => {
    if (toIndex < 0 || toIndex >= connections.length) return
    const updated = [...connections]
    const a = updated[fromIndex]
    const b = updated[toIndex]
    const tmpPriority = a.priority ?? 0
    a.priority = b.priority ?? 0
    b.priority = tmpPriority
    updated.sort((x, y) => (x.priority ?? 0) - (y.priority ?? 0))
    setConnections(updated)
    providersApi.updateProvider(a.id, { priority: a.priority }).catch(() => {})
    providersApi.updateProvider(b.id, { priority: b.priority }).catch(() => {})
  }

  const handleToggleActive = async (connId, isActive) => {
    const conn = connections.find(c => c.id === connId)
    if (!conn) return
    const updated = { ...conn, is_active: !isActive }
    setConnections(prev => prev.map(c => c.id === connId ? updated : c))
    try { await providersApi.updateProvider(connId, { is_active: !isActive }) }
    catch { setConnections(prev => prev.map(c => c.id === connId ? conn : c)) }
  }

  const handleDelete = async (connId) => {
    setConfirmState({ type: 'deleteConnection', id: connId })
  }

  const confirmDelete = async () => {
    if (!confirmState) return
    const { id } = confirmState
    setConfirmState(null)
    const prev = connections
    setConnections(p => p.filter(c => c.id !== id))
    try { await providersApi.deleteProvider(id) }
    catch { setConnections(prev) }
  }

  const handleTestConnectionRow = async (connId) => {
    setTestingConnectionId(connId)
    setTestResults(prev => ({ ...prev, [connId]: null }))
    try {
      const res = await providersApi.testProvider(connId)
      setTestResults(prev => ({ ...prev, [connId]: res.data }))
    } catch (err) {
      setTestResults(prev => ({ ...prev, [connId]: { valid: false, error: err.message } }))
    } finally {
      setTestingConnectionId(null)
    }
  }

  const handleFetchModels = async () => {
    if (!providerConns.length) return
    setFetchingModels(true)
    try {
      await providersApi.fetchProviderModels(providerConns[0].id)
      await fetchConnections()
    } catch (err) { console.error('Fetch models failed:', err) }
    finally { setFetchingModels(false) }
  }

  const handleClearModels = async () => {
    if (!providerConns.length) return
    setClearingModels(true)
    try {
      await providersApi.clearProviderModels(providerConns[0].id)
      await fetchConnections()
    } catch (err) { console.error('Clear models failed:', err) }
    finally { setClearingModels(false) }
  }

  const handleTestModel = async (modelId) => {
    setTestingModelId(modelId)
    setModelTestResults(prev => ({ ...prev, [modelId]: null }))
    try {
      const fullModel = `${providerAlias}/${modelId}`
      const token = useAuthStore.getState().token
      const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token || ''}` }

      // Dispatch endpoint+body based on route kind
      // (page-level: this entire page is scoped to one kind via /media-providers/:kind/:providerId)
      let endpoint, body, isMultipart = false
      if (kind === 'embedding') {
        endpoint = '/v1/embeddings'
        body = { model: fullModel, input: 'test' }
      } else if (kind === 'tts') {
        endpoint = '/v1/audio/speech'
        body = { model: fullModel, input: 'test', voice: 'alloy' }
      } else if (kind === 'stt') {
        endpoint = '/v1/audio/transcriptions'
        // Build a minimal silent WAV (~0.1s @ 8kHz mono 16-bit) for connectivity test
        const sampleRate = 8000, durationSec = 0.1
        const numSamples = Math.floor(sampleRate * durationSec)
        const dataSize = numSamples * 2
        const buf = new ArrayBuffer(44 + dataSize)
        const view = new DataView(buf)
        const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)) }
        writeStr(0, 'RIFF'); view.setUint32(4, 36 + dataSize, true); writeStr(8, 'WAVE')
        writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true)
        view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true)
        view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
        writeStr(36, 'data'); view.setUint32(40, dataSize, true)
        const fd = new FormData()
        fd.append('file', new Blob([buf], { type: 'audio/wav' }), 'test.wav')
        fd.append('model', fullModel)
        fd.append('response_format', 'json')
        body = fd
        isMultipart = true
      } else if (kind === 'image') {
        endpoint = '/v1/images/generations'
        body = { model: fullModel, prompt: 'test', n: 1 }
      } else {
        // Default: LLM chat completions (covers kind=undefined and any llm-shaped kinds)
        endpoint = '/v1/chat/completions'
        body = { model: fullModel, messages: [{ role: 'user', content: 'Say OK' }], max_tokens: 5 }
      }

      const fetchOpts = isMultipart
        ? { method: 'POST', headers: { 'Authorization': headers['Authorization'] }, body }
        : { method: 'POST', headers, body: JSON.stringify(body) }
      const res = await fetch(endpoint, fetchOpts)
      setModelTestResults(prev => ({ ...prev, [modelId]: res.ok ? 'ok' : 'error' }))
    } catch {
      setModelTestResults(prev => ({ ...prev, [modelId]: 'error' }))
    } finally {
      setTestingModelId(null)
    }
  }

  const handleDisableModel = async (modelId) => {
    try {
      const { default: client } = await import('../api/client')
      await client.post('/models/disabled', { providerAlias, ids: [modelId] })
      setDisabledModelIds(prev => [...prev, modelId])
    } catch (e) { console.error('Disable failed:', e) }
  }

  const handleEnableModel = async (modelId) => {
    try {
      const { default: client } = await import('../api/client')
      await client.delete('/models/disabled', { params: { providerAlias, id: modelId } })
      setDisabledModelIds(prev => prev.filter(id => id !== modelId))
    } catch {}
  }

  const handleDisableAll = async (ids) => {
    if (!ids.length) return
    if (!window.confirm(`Disable all ${ids.length} model(s)?`)) return
    try {
      const { default: client } = await import('../api/client')
      await client.post('/models/disabled', { providerAlias, ids })
      setDisabledModelIds(prev => Array.from(new Set([...prev, ...ids])))
    } catch (e) { console.error('Disable all failed:', e) }
  }

  const handleEnableAll = async () => {
    try {
      const { default: client } = await import('../api/client')
      await client.delete('/models/disabled', { params: { providerAlias } })
      setDisabledModelIds([])
    } catch (e) { console.error('Enable all failed:', e) }
  }

  const handleAddCustomModel = async (cleanId) => {
    try {
      const { default: client } = await import('../api/client')
      // Reuse same endpoint as LLM page — alias defaults to model id
      await client.put('/models/alias', { model: `${providerAlias}/${cleanId}`, alias: cleanId })
      setShowAddCustomModel(false)
      await fetchModels()
    } catch (e) { console.error('Add custom model failed:', e) }
  }

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

  // Filter models by route kind (e.g. only embedding models on /media-providers/embedding/<id>).
  // Uses getModelType which checks user override → model.type → regex inference.
  const kindFilteredModels = kind
    ? models.filter((m) => {
        const mid = typeof m === 'string' ? m : m.id
        return getModelType(mid) === kind
      })
    : models

  const handleStrategyChange = async (newStrategy) => {
    const strategy = newStrategy === 'fill-first' ? null : newStrategy
    if (strategy === 'round-robin' && !providerStickyLimit) setProviderStickyLimit('1')
    setProviderStrategy(strategy)
    try {
      const settingsRes = await settingsApi.get()
      const settingsData = settingsRes.data || {}
      const strategies = settingsData.providerStrategies || settingsData.provider_strategies || {}
      if (strategy) {
        const override = { ...(strategies[providerId] || {}), fallbackStrategy: strategy }
        if (strategy === 'round-robin') {
          override.stickyRoundRobinLimit = Number(providerStickyLimit) || 1
        }
        strategies[providerId] = override
      } else {
        delete strategies[providerId]?.fallbackStrategy
        if (!Object.keys(strategies[providerId] || {}).length) delete strategies[providerId]
      }
      await settingsApi.update({ providerStrategies: strategies })
    } catch {}
  }

  const handleStickyLimitChange = async (val) => {
    setProviderStickyLimit(val)
    try {
      const settingsRes = await settingsApi.get()
      const settingsData = settingsRes.data || {}
      const strategies = settingsData.providerStrategies || settingsData.provider_strategies || {}
      strategies[providerId] = { ...(strategies[providerId] || {}), stickyRoundRobinLimit: Number(val) || 1 }
      await settingsApi.update({ providerStrategies: strategies })
    } catch {}
  }

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  if (!provider) {
    return (
      <div className="text-center py-20">
        <p className="text-zinc-400">Provider not found</p>
        <Link to={`/media-providers/${kind || 'embedding'}`} className="text-primary-400 hover:underline text-sm mt-2 inline-block">Back to Media Providers</Link>
      </div>
    )
  }

  return (
    <div className="flex min-w-0 flex-col gap-6 px-1 sm:gap-8 sm:px-0">
      {/* ── Header ── */}
      <div className="min-w-0">
        <Link to={`/media-providers/${kind || 'embedding'}`}
          className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-primary-400 transition-colors mb-4">
          <ArrowLeft size={16} /> Back to {kindConfig?.label || kind}
        </Link>
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          {headerImgError ? (
            <div className="flex size-12 shrink-0 items-center justify-center rounded-lg text-base font-bold"
              style={{ backgroundColor: `${provider.color || '#71717A'}15`, color: provider.color || '#71717A' }}>
              {provider.icon || providerId.slice(0, 2).toUpperCase()}
            </div>
          ) : (
            <img src={`/providers/${providerId}.png`} alt={provider.name} width={48} height={48}
              className="size-12 shrink-0 rounded-lg object-contain" onError={() => setHeaderImgError(true)} />
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="truncate text-2xl font-semibold tracking-tight text-zinc-100 sm:text-3xl">{provider.name}</h1>
              {provider.notice?.apiKeyUrl && (
                <a href={provider.notice.apiKeyUrl} target="_blank" rel="noopener noreferrer"
                  className="text-xs text-primary-400 hover:underline inline-flex items-center gap-1">
                  <ExternalLink size={12} /> Get API Key
                </a>
              )}
              {allServiceKinds.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {allServiceKinds.map(k => (
                    <span key={k} className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${TYPE_BADGE_STYLES[k] || TYPE_BADGE_STYLES.llm}`}>{k}</span>
                  ))}
                </div>
              )}
            </div>
            <p className="text-zinc-500">{connections.length} connection{connections.length === 1 ? '' : 's'} configured</p>
          </div>
        </div>
      </div>

      {/* ── Provider notice ── */}
      {provider.notice?.text && (
        <div className="flex items-start gap-3 px-4 py-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
          <Info size={14} className="text-blue-400 mt-0.5 shrink-0" />
          <p className="text-xs text-blue-300 leading-relaxed">{provider.notice.text}</p>
        </div>
      )}

      {/* ── Connections Card ── */}
      <Card>
        <CardContent>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-semibold text-zinc-100">Connections</h2>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
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
                    <input type="number" min={1} value={providerStickyLimit}
                      onChange={(e) => handleStickyLimitChange(e.target.value)} placeholder="1"
                      className="w-14 px-2 py-1 text-xs border border-zinc-700 rounded-md bg-zinc-800/50 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500" />
                  </div>
                )}
              </div>
            </div>
          </div>

          {connections.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-primary-600/10 text-primary-400 mb-4">
                <Key size={20} />
              </div>
              <p className="text-sm text-zinc-400 mb-4">No connections yet</p>
              <Button size="sm" onClick={() => setShowAddModal(true)}>
                <Plus size={14} /> Add Connection
              </Button>
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
                        onMoveUp={() => handleSwapPriority(index, index - 1)}
                        onMoveDown={() => handleSwapPriority(index, index + 1)}
                        onToggleActive={(isActive) => handleToggleActive(conn.id, isActive)}
                        onUpdateProxy={async (proxyPoolId) => {
                          try {
                            await providersApi.updateProvider(conn.id, { proxyPoolId: proxyPoolId || null })
                            setConnections(prev => prev.map(c => c.id === conn.id ? { ...c, proxy_pool_id: proxyPoolId || null } : c))
                          } catch (error) { console.error('Error updating proxy:', error) }
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
                <Button size="sm" onClick={() => setShowAddModal(true)}>
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
            {models.length > 0 && (() => {
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
            {models.length === 0 && connections.length > 0 && (
              <Button size="sm" variant="secondary" onClick={handleFetchModels} disabled={fetchingModels}>
                {fetchingModels ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                {fetchingModels ? 'Fetching...' : 'Fetch Models'}
              </Button>
            )}
          </div>

          {kindFilteredModels.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10">
              <p className="text-sm text-zinc-500 text-center">
                {models.length > 0 && kind
                  ? <>No {kindConfig?.label?.toLowerCase() || kind} models. Provider has {models.length} model(s) of other types — visit <Link to={`/providers/${providerId}`} className="text-primary-400 hover:underline">/providers/{providerId}</Link> to see all.</>
                  : 'No models. Fetch from provider after adding a connection.'}
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {/* Active (enabled) models */}
              {(() => {
                const disabledSet = new Set(disabledModelIds)
                const searchQ = modelSearchQuery.trim().toLowerCase()
                const activeModels = kindFilteredModels.filter((m) => {
                  const mid = typeof m === 'string' ? m : m.id
                  return !disabledSet.has(mid) && (!searchQ || mid.toLowerCase().includes(searchQ))
                })
                return activeModels.map((model) => {
                  const modelId = typeof model === 'string' ? model : model.id
                  const fullModelStr = `${providerAlias}/${modelId}`
                  return (
                    <ModelRow
                      key={modelId}
                      model={typeof model === 'string' ? { id: model } : model}
                      fullModel={fullModelStr}
                      copied={copied}
                      onCopy={handleCopy}
                      testStatus={modelTestResults[modelId]}
                      onTest={connections.length > 0 ? () => handleTestModel(modelId) : undefined}
                      isTesting={testingModelId === modelId}
                      onDisable={() => handleDisableModel(modelId)}
                      modelType={getModelType(modelId)}
                      onTypeChange={connections.length > 0 ? (newType) => handleChangeModelType(modelId, newType) : undefined}
                    />
                  )
                })
              })()}

              {/* Search input — applies to all lists */}
              {models.length > 0 && (
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

              {/* Add Model button — always after search input */}
              <button
                onClick={() => setShowAddCustomModel(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-primary-500/40 px-3 py-2 text-xs text-primary-400 transition-colors hover:border-primary-500 hover:bg-primary-500/5 sm:w-auto"
              >
                <Plus size={14} /> Add Model
              </button>

              {/* Suggestions: disabled models go back here (kind-filtered) */}
              {(() => {
                const disabledSet = new Set(disabledModelIds)
                const searchQ = modelSearchQuery.trim().toLowerCase()
                const disabledModels = kindFilteredModels.filter((m) => {
                  const mid = typeof m === 'string' ? m : m.id
                  return disabledSet.has(mid) && (!searchQ || mid.toLowerCase().includes(searchQ))
                })
                if (disabledModels.length === 0) return null
                return (
                  <div className="w-full mt-2">
                    <p className="text-xs text-zinc-500 mb-2">Available to enable ({disabledModels.length}):</p>
                    <div className="flex flex-wrap gap-1.5">
                      {disabledModels.map((m) => {
                        const modelId = typeof m === 'string' ? m : m.id
                        return (
                          <button
                            key={modelId}
                            onClick={() => handleEnableModel(modelId)}
                            className="inline-flex items-center gap-1 rounded-md border border-dashed border-zinc-700 px-2 py-1 text-xs text-zinc-400 hover:border-primary-500/50 hover:text-primary-400 hover:bg-primary-900/10 transition-colors"
                          >
                            <Plus size={10} /> {modelId}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })()}

            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Test Playground (kind-aware) ── */}
      {kind === 'tts' ? (
        <TtsTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />
      ) : kind === 'stt' ? (
        <SttTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />
      ) : kind === 'webSearch' ? (
        <SearchTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />
      ) : kind === 'image' ? (
        <ImageTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />
      ) : kind === 'embedding' ? (
        <EmbeddingTestPlayground providerId={providerId} providerAlias={providerAlias} connections={connections} />
      ) : (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="py-8 text-center text-sm text-zinc-500">
            Playground not available for this kind
          </CardContent>
        </Card>
      )}

      {/* ── Modals ── */}
      <AddKeyModal isOpen={showAddModal} onClose={() => setShowAddModal(false)} onCreated={fetchConnections}
        providerId={providerId} provider={provider} proxyPools={proxyPools} />

      <AddKeyModal isOpen={showEditModal} onClose={() => { setShowEditModal(false); setSelectedConnection(null) }}
        onCreated={fetchConnections} providerId={providerId} provider={provider} editConnection={selectedConnection} proxyPools={proxyPools} />

      <ConfirmModal isOpen={!!confirmState} onClose={() => setConfirmState(null)} onConfirm={confirmDelete}
        title="Delete Connection" message="Are you sure you want to delete this connection? This cannot be undone." />

      <AddCustomModelModal
        isOpen={showAddCustomModel}
        providerAlias={providerAlias}
        onSave={handleAddCustomModel}
        onClose={() => setShowAddCustomModel(false)}
      />
    </div>
  )
}
