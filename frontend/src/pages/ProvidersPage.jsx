import { useState, useEffect, useCallback, useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Plus, Search, Server, Plug, AlertCircle, ChevronRight, Key, Play,
  CheckCircle, XCircle, Loader2, Expand, Settings2, ToggleLeft, ToggleRight,
  X, Zap, Shield, Globe, Wifi,
} from 'lucide-react'
import Card, { CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import ModelAvailabilityBadge from '../components/ModelAvailabilityBadge'
import OAuthModal from '../components/OAuthModal'
import AddOpenAICompatibleModal from '../components/modals/AddOpenAICompatibleModal'
import AddAnthropicCompatibleModal from '../components/modals/AddAnthropicCompatibleModal'
import { providersApi } from '../api/providers'
import useCatalogStore from '../stores/catalogStore'
import { useNotificationStore } from '../stores/notificationStore'

// ── Provider categorization (using catalog store) ────────────────────────────
function isLLMProvider(info) {
  if (!info.serviceKinds) return true
  return info.serviceKinds.includes('llm')
}

function isOAuthProvider(key) {
  const p = useCatalogStore.getState().providers[key]
  return p?.authType === 'oauth'
}

function isFreeProvider(key) {
  const p = useCatalogStore.getState().providers[key]
  return p?.authType === 'free' || p?.noAuth === true
}

function isFreeTierProvider(key) {
  const cats = useCatalogStore.getState().categories
  return (cats.freeTier || []).includes(key)
}

function isWebCookieProvider(key) {
  const p = useCatalogStore.getState().providers[key]
  return p?.authType === 'cookie'
}

function isApiKeyProvider(key) {
  const p = useCatalogStore.getState().providers[key]
  return p?.authType === 'apikey'
}

function getAuthType(providerId, provider) {
  const p = provider || useCatalogStore.getState().providers[providerId]
  if (p?.noAuth) return 'free'
  if (p?.authType) return p.authType
  return 'apikey'
}

// ── Error classification helpers ─────────────────────────────────────────────
function getConnectionErrorTag(conn) {
  if (!conn) return null
  const explicitType = conn.last_error_type || conn.lastErrorType
  if (explicitType === 'runtime_error') return 'RUNTIME'
  if (['upstream_auth_error', 'auth_missing', 'token_refresh_failed', 'token_expired'].includes(explicitType)) return 'AUTH'
  if (explicitType === 'upstream_rate_limited') return '429'
  if (explicitType === 'upstream_unavailable') return '5XX'
  if (explicitType === 'network_error') return 'NET'

  const numericCode = Number(conn.error_code || conn.errorCode)
  if (Number.isFinite(numericCode) && numericCode >= 400) return String(numericCode)

  const msg = (conn.last_error || conn.lastError || '').toLowerCase()
  if (msg.includes('runtime') || msg.includes('not runnable') || msg.includes('not installed')) return 'RUNTIME'
  if (msg.includes('invalid api key') || msg.includes('token invalid') || msg.includes('revoked') || msg.includes('unauthorized')) return 'AUTH'

  return 'ERR'
}

function getRelativeTime(dateStr) {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

const APIKEY_INITIAL_VISIBLE = 20

// ── Provider logo image with text-icon fallback ───────────────────────────
function ProviderLogo({ providerId, provider, size = 32 }) {
  const [imgError, setImgError] = useState(false)
  const src = `/providers/${providerId}.png`

  if (imgError) {
    return (
      <div
        className="shrink-0 rounded-lg flex items-center justify-center text-xs font-bold"
        style={{
          width: size, height: size,
          backgroundColor: (provider.color || '#666') + '20',
          color: provider.color || '#999',
        }}
      >
        {provider.textIcon || provider.icon || providerId.slice(0, 2).toUpperCase()}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={provider.name || providerId}
      width={size}
      height={size}
      className="shrink-0 rounded-lg object-contain"
      style={{ width: size, height: size }}
      onError={() => setImgError(true)}
    />
  )
}

// ── Main page component ─────────────────────────────────────────────────────
export default function ProvidersPage() {
  const [connections, setConnections] = useState([])
  const [providerNodes, setProviderNodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [showAllApikey, setShowAllApikey] = useState(false)
  const [showAddCompatibleModal, setShowAddCompatibleModal] = useState(false)
  const [showAddAnthropicModal, setShowAddAnthropicModal] = useState(false)
  const [showAddKeyModal, setShowAddKeyModal] = useState(false)
  const [addKeyProvider, setAddKeyProvider] = useState('')
  const [testingMode, setTestingMode] = useState(null)
  const [testResults, setTestResults] = useState(null)
  const [oauthModalProvider, setOauthModalProvider] = useState(null)
  const [autoConnectingProvider, setAutoConnectingProvider] = useState(null)

  const addNotification = useNotificationStore(s => s.addNotification)
  const location = useLocation()

  // ── Data fetching ──────────────────────────────────────────────────────────
  const fetchData = useCallback(async () => {
    try {
      const [connRes, nodesRes] = await Promise.all([
        providersApi.getProviders({ kind: 'llm' }),
        providersApi.getProviderNodes(),
      ])
      setConnections(connRes.data?.connections || connRes.data || [])
      setProviderNodes(nodesRes.data?.nodes || nodesRes.data || [])
    } catch (err) {
      console.error('Failed to fetch providers:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])
  useEffect(() => { fetchData() }, [location.pathname])

  // ── Provider stats computation ─────────────────────────────────────────────
  const getProviderStats = useCallback((providerId) => {
    const conns = connections.filter(c => c.provider === providerId)

    const connected = conns.filter(c => {
      const status = c.test_status || c.testStatus
      return status === 'active' || status === 'success' || status === 'connected'
    }).length

    const errorConns = conns.filter(c => {
      const status = c.test_status || c.testStatus
      return status === 'error' || status === 'expired' || status === 'unavailable'
    })

    const error = errorConns.length
    const total = conns.length
    const allDisabled = total > 0 && conns.every(c => c.is_active === false || c.isActive === false)

    const latestError = errorConns.sort((a, b) =>
      new Date(b.last_error_at || b.lastErrorAt || 0) - new Date(a.last_error_at || a.lastErrorAt || 0)
    )[0]
    const errorCode = latestError ? getConnectionErrorTag(latestError) : null
    const errorTime = latestError?.last_error_at || latestError?.lastErrorAt
      ? getRelativeTime(latestError.last_error_at || latestError.lastErrorAt)
      : null

    return { connected, error, total, errorCode, errorTime, allDisabled }
  }, [connections])

  // ── Toggle handler ─────────────────────────────────────────────────────────
  const handleToggleProvider = useCallback(async (providerId, newActive) => {
    const providerConns = connections.filter(c => c.provider === providerId)
    // optimistic update
    setConnections(prev => prev.map(c =>
      c.provider === providerId ? { ...c, is_active: newActive, isActive: newActive } : c
    ))
    try {
      const results = await Promise.allSettled(
        providerConns.map(c => providersApi.updateProvider(c.id, { is_active: newActive }))
      )
      const anyFailed = results.some(r => r.status === 'rejected')
      if (anyFailed) {
        // revert optimistic update
        setConnections(prev => prev.map(c =>
          c.provider === providerId ? { ...c, is_active: !newActive, isActive: !newActive } : c
        ))
        addNotification({ type: 'error', message: 'Failed to update provider status' })
      }
    } catch {
      setConnections(prev => prev.map(c =>
        c.provider === providerId ? { ...c, is_active: !newActive, isActive: !newActive } : c
      ))
      addNotification({ type: 'error', message: 'Failed to update provider status' })
    }
  }, [connections, addNotification])

  // ── Batch test handler ─────────────────────────────────────────────────────
  const handleBatchTest = useCallback(async (mode, providerId = null) => {
    if (testingMode) return
    setTestingMode(providerId || mode)
    setTestResults(null)
    try {
      const allConns = providerId
        ? connections.filter(c => c.provider === providerId)
        : connections.filter(c => {
            const key = c.provider
            if (mode === 'oauth') return isOAuthProvider(key)
            if (mode === 'free') return isFreeProvider(key) || isFreeTierProvider(key)
            if (mode === 'cookie') return isWebCookieProvider(key)
            if (mode === 'apikey') return isApiKeyProvider(key)
            return true
          })

      const results = await Promise.allSettled(
        allConns.map(async (conn) => {
          const start = Date.now()
          try {
            await providersApi.validateProvider({
              provider: conn.provider,
              apiKey: conn.api_key_masked || '',
            })
            return {
              connectionId: conn.id,
              connectionName: conn.name || conn.provider,
              provider: conn.provider,
              valid: true,
              latencyMs: Date.now() - start,
            }
          } catch (err) {
            return {
              connectionId: conn.id,
              connectionName: conn.name || conn.provider,
              provider: conn.provider,
              valid: false,
              latencyMs: Date.now() - start,
              diagnosis: { type: 'ERROR' },
            }
          }
        })
      )

      const items = results.map(r => r.value || r.reason)
      const passed = items.filter(r => r.valid).length
      const failed = items.filter(r => !r.valid).length

      const data = { mode, results: items, summary: { passed, failed, total: items.length } }
      setTestResults(data)

      if (failed === 0) {
        addNotification({ type: 'success', message: `All ${items.length} tests passed` })
      } else {
        addNotification({ type: 'warning', message: `${passed}/${items.length} passed, ${failed} failed` })
      }
    } catch {
      setTestResults({ error: 'Test request failed' })
      addNotification({ type: 'error', message: 'Provider test failed' })
    } finally {
      setTestingMode(null)
    }
  }, [testingMode, connections, addNotification])

  // ── Match search ───────────────────────────────────────────────────────────
  const matchSearch = useCallback((name) => {
    if (!searchQuery.trim()) return true
    return name.toLowerCase().includes(searchQuery.trim().toLowerCase())
  }, [searchQuery])

  // ── Categorize provider entries ────────────────────────────────────────────
  const compatibleProviders = providerNodes
    .filter(n => n.type === 'openai-compatible')
    .map(n => ({
      id: n.id,
      name: n.name || 'OpenAI Compatible',
      color: '#10A37F',
      textIcon: 'OC',
      apiType: n.api_type || n.apiType || 'chat',
      baseUrl: n.base_url || n.baseUrl,
    }))
    .filter(p => matchSearch(p.name))

  const anthropicCompatibleProviders = providerNodes
    .filter(n => n.type === 'anthropic-compatible')
    .map(n => ({
      id: n.id,
      name: n.name || 'Anthropic Compatible',
      color: '#D97757',
      textIcon: 'AC',
      baseUrl: n.base_url || n.baseUrl,
    }))
    .filter(p => matchSearch(p.name))

  const catalog = useCatalogStore((s) => s.providers)
  const categories = useCatalogStore((s) => s.categories)

  const sortByStats = (entries) =>
    [...entries].sort(([ka], [kb]) => {
      const sa = getProviderStats(ka)
      const sb = getProviderStats(kb)
      const ca = sa.connected > 0 ? 1 : 0
      const cb = sb.connected > 0 ? 1 : 0
      if (ca !== cb) return cb - ca
      return (catalog[ka]?.name || ka).localeCompare(catalog[kb]?.name || kb)
    })

  const oauthEntries = (categories.oauth || [])
    .map(id => [id, catalog[id]])
    .filter(([, info]) => info && !info.hidden && isLLMProvider(info) && matchSearch(info.name))

  const freeEntries = (categories.free || [])
    .map(id => [id, catalog[id]])
    .filter(([, info]) => info && !info.hidden && isLLMProvider(info) && matchSearch(info.name))

  const freeTierEntries = (categories.freeTier || [])
    .map(id => [id, catalog[id]])
    .filter(([, info]) => info && !info.hidden && isLLMProvider(info) && matchSearch(info.name))

  const cookieEntries = (categories.webCookie || [])
    .map(id => [id, catalog[id]])
    .filter(([, info]) => info && !info.hidden && isLLMProvider(info) && matchSearch(info.name))

  const apikeyEntries = sortByStats(
    (categories.apiKey || [])
      .map(id => [id, catalog[id]])
      .filter(([, info]) => info && !info.hidden && isLLMProvider(info) && matchSearch(info.name))
  )

  const isSearching = !!searchQuery.trim()
  const visibleApikeyEntries = isSearching || showAllApikey
    ? apikeyEntries
    : apikeyEntries.slice(0, APIKEY_INITIAL_VISIBLE)
  const hiddenApikeyCount = apikeyEntries.length - APIKEY_INITIAL_VISIBLE

  const hasAnyResult =
    oauthEntries.length > 0 ||
    freeEntries.length > 0 ||
    freeTierEntries.length > 0 ||
    cookieEntries.length > 0 ||
    apikeyEntries.length > 0 ||
    compatibleProviders.length > 0 ||
    anthropicCompatibleProviders.length > 0

  // ── Open add key modal ─────────────────────────────────────────────────────
  const openAddKeyModal = (providerKey) => {
    setAddKeyProvider(providerKey)
    setShowAddKeyModal(true)
  }

  const handleAutoConnect = async (providerKey) => {
    setAutoConnectingProvider(providerKey)
    try {
      await providersApi.createProvider({
        provider: providerKey,
        auth_type: 'free',
        noAuth: true,
        priority: 1,
      })
      fetchData()
    } catch (err) {
      console.error('Auto-connect failed:', err)
    } finally {
      setAutoConnectingProvider(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-8">
        {[1, 2, 3].map(i => (
          <div key={i} className="animate-pulse">
            <div className="h-6 w-48 bg-zinc-800 rounded mb-4" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {[1, 2, 3].map(j => (
                <div key={j} className="h-16 bg-zinc-800/50 rounded-xl" />
              ))}
            </div>
          </div>
        ))}
      </div>
    )
  }

  // ── Test All button helper ─────────────────────────────────────────────────
  const TestAllButton = ({ mode, label }) => (
    <button
      onClick={() => handleBatchTest(mode)}
      disabled={!!testingMode}
      className={`flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors sm:w-auto sm:py-1.5 cursor-pointer ${
        testingMode === mode
          ? 'bg-primary-500/20 border-primary-500/40 text-primary-400 animate-pulse'
          : 'bg-zinc-800/50 border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-primary-500/40'
      }`}
      title={`Test all ${label} connections`}
    >
      {testingMode === mode ? (
        <Loader2 size={14} className="animate-spin" />
      ) : (
        <Play size={14} />
      )}
      {testingMode === mode ? 'Testing...' : 'Test All'}
    </button>
  )

  // ── Section header helper ──────────────────────────────────────────────────
  const SectionHeader = ({ title, children }) => (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <h2 className="text-lg sm:text-xl font-semibold text-zinc-100 flex items-center gap-2 leading-tight">
        {title}
      </h2>
      <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
        {children}
      </div>
    </div>
  )

  return (
    <div className="flex min-w-0 flex-col gap-6">
      {/* ── Header with search ────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Providers</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {connections.length} connection{connections.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ModelAvailabilityBadge />
          <div className="relative w-full sm:w-64">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search providers..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors hover:border-zinc-600"
            />
          </div>
        </div>
      </div>

      {/* ── No results ────────────────────────────────────────────────────────── */}
      {!hasAnyResult && (
        <div className="text-center py-8 border border-dashed border-zinc-700 rounded-xl">
          <Search size={32} className="mx-auto text-zinc-600 mb-2" />
          <p className="text-zinc-400 text-sm">No providers match your search</p>
        </div>
      )}

      {/* ── Custom Providers (OpenAI/Anthropic Compatible) ───────────────────── */}
      <div className="flex flex-col gap-4">
        <SectionHeader title="Custom Providers">
          <Button
            size="sm"
            onClick={() => setShowAddAnthropicModal(true)}
          >
            <Plus size={14} />
            Add Anthropic Compatible
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowAddCompatibleModal(true)}
          >
            <Plus size={14} />
            Add OpenAI Compatible
          </Button>
        </SectionHeader>

        {compatibleProviders.length === 0 && anthropicCompatibleProviders.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-3 border border-dashed border-zinc-700 rounded-xl text-zinc-500 text-sm">
            <Settings2 size={16} />
            <span>No custom providers — use buttons above to add OpenAI/Anthropic compatible endpoints</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {[...compatibleProviders, ...anthropicCompatibleProviders].map(info => (
              <ApiKeyProviderCard
                key={info.id}
                providerId={info.id}
                provider={info}
                stats={getProviderStats(info.id)}
                authType="compatible"
                onToggle={(active) => handleToggleProvider(info.id, active)}
                onAddKey={() => openAddKeyModal(info.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── OAuth Providers ───────────────────────────────────────────────────── */}
      {oauthEntries.length > 0 && (
        <div className="flex flex-col gap-4">
          <SectionHeader title="OAuth Providers">
            <TestAllButton mode="oauth" label="OAuth" />
          </SectionHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {oauthEntries.map(([key, info]) => {
              const authType = getAuthType(key, info)
              return (
                <ProviderCard
                  key={key}
                  providerId={key}
                  provider={{ id: key, ...info }}
                  stats={getProviderStats(key)}
                  authType={authType}
                  onToggle={(active) => handleToggleProvider(key, active)}
                  onConnect={() => {
                    if (info.noAuth) {
                      handleAutoConnect(key)
                    } else {
                      setOauthModalProvider({ id: key, ...info })
                    }
                  }}
                  onAddKey={() => openAddKeyModal(key)}
                />
              )
            })}
          </div>
        </div>
      )}

      {/* ── Free Tier Providers ───────────────────────────────────────────────── */}
      {(freeEntries.length > 0 || freeTierEntries.length > 0) && (
        <div className="flex flex-col gap-4">
          <SectionHeader title="Free Tier Providers">
            <TestAllButton mode="free" label="Free" />
          </SectionHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {freeEntries.map(([key, info]) => {
              const authType = getAuthType(key, info)
              return (
                <ProviderCard
                  key={key}
                  providerId={key}
                  provider={{ id: key, ...info }}
                  stats={getProviderStats(key)}
                  authType={authType}
                  onToggle={(active) => handleToggleProvider(key, active)}
                  onConnect={() => {
                    if (info.noAuth) {
                      handleAutoConnect(key)
                    } else {
                      setOauthModalProvider({ id: key, ...info })
                    }
                  }}
                  onAddKey={() => openAddKeyModal(key)}
                />
              )
            })}
            {freeTierEntries.map(([key, info]) => (
              <ApiKeyProviderCard
                key={key}
                providerId={key}
                provider={{ id: key, ...info }}
                stats={getProviderStats(key)}
                authType="apikey"
                onToggle={(active) => handleToggleProvider(key, active)}
                onAddKey={() => openAddKeyModal(key)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── API Key Providers ─────────────────────────────────────────────────── */}
      {apikeyEntries.length > 0 && (
        <div className="flex flex-col gap-4">
          <SectionHeader title="API Key Providers">
            <TestAllButton mode="apikey" label="API Key" />
          </SectionHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {visibleApikeyEntries.map(([key, info]) => (
              <ApiKeyProviderCard
                key={key}
                providerId={key}
                provider={{ id: key, ...info }}
                stats={getProviderStats(key)}
                authType="apikey"
                onToggle={(active) => handleToggleProvider(key, active)}
                onAddKey={() => openAddKeyModal(key)}
              />
            ))}
          </div>
          {!isSearching && !showAllApikey && hiddenApikeyCount > 0 && (
            <button
              onClick={() => setShowAllApikey(true)}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-primary-500/40 px-3 py-2.5 text-sm font-medium text-primary-400 transition-colors hover:border-primary-500 hover:bg-primary-500/5 cursor-pointer"
            >
              <Expand size={16} />
              Show all {apikeyEntries.length} providers
            </button>
          )}
        </div>
      )}

      {/* ── Web Cookie Providers ──────────────────────────────────────────────── */}
      {cookieEntries.length > 0 && (
        <div className="flex flex-col gap-4">
          <SectionHeader title="Web Cookie Providers">
            <TestAllButton mode="cookie" label="Cookie" />
          </SectionHeader>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4">
            {cookieEntries.map(([key, info]) => (
              <CookieProviderCard
                key={key}
                providerId={key}
                provider={{ id: key, ...info }}
                stats={getProviderStats(key)}
                onToggle={(active) => handleToggleProvider(key, active)}
                onAddKey={() => openAddKeyModal(key)}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Modals ────────────────────────────────────────────────────────────── */}
      <AddOpenAICompatibleModal
        isOpen={showAddCompatibleModal}
        onClose={() => setShowAddCompatibleModal(false)}
        onCreated={(node) => {
          setProviderNodes(prev => [...prev, node])
          setShowAddCompatibleModal(false)
        }}
      />
      <AddAnthropicCompatibleModal
        isOpen={showAddAnthropicModal}
        onClose={() => setShowAddAnthropicModal(false)}
        onCreated={(node) => {
          setProviderNodes(prev => [...prev, node])
          setShowAddAnthropicModal(false)
        }}
      />
      <AddApiKeyModal
        isOpen={showAddKeyModal}
        providerKey={addKeyProvider}
        onClose={() => { setShowAddKeyModal(false); setAddKeyProvider('') }}
        onCreated={() => { setShowAddKeyModal(false); setAddKeyProvider(''); fetchData() }}
      />
      {oauthModalProvider && (
        <OAuthModal
          isOpen={!!oauthModalProvider}
          onClose={() => setOauthModalProvider(null)}
          provider={oauthModalProvider.id}
          providerInfo={oauthModalProvider}
          onSuccess={() => { setOauthModalProvider(null); fetchData() }}
        />
      )}

      {/* ── Test Results Modal ────────────────────────────────────────────────── */}
      {testResults && (
        <Modal
          isOpen={!!testResults}
          onClose={() => setTestResults(null)}
          title="Test Results"
        >
          <ProviderTestResultsView results={testResults} />
        </Modal>
      )}
    </div>
  )
}

// ── Provider Card (unified for OAuth, Free, noAuth) ─────────────────────────
function ProviderCard({ providerId, provider, stats, authType, onToggle, onConnect, onAddKey }) {
  const { connected, error, errorCode, errorTime, allDisabled } = stats
  const isNoAuth = authType === 'free'

  const dotColors = {
    free: 'bg-emerald-500',
    oauth: 'bg-blue-500',
    apikey: 'bg-amber-500',
    cookie: 'bg-purple-500',
  }
  const dotLabels = {
    free: 'Free',
    oauth: 'OAuth',
    apikey: 'API Key',
    cookie: 'Cookie',
  }

  return (
    <Link to={`/providers/${providerId}`} className="group min-w-0">
      <Card className={`h-full hover:border-zinc-600/80 transition-all duration-150 hover:bg-zinc-800/20 cursor-pointer ${allDisabled ? 'opacity-50' : ''}`}>
        <CardContent className="p-4">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <ProviderLogo providerId={providerId} provider={provider} size={32} />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">{provider.name}</h3>
                <div className="flex min-w-0 items-center gap-1.5 text-xs flex-wrap mt-0.5">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotColors[authType] || 'bg-zinc-500'}`} title={dotLabels[authType] || authType} />
                  {allDisabled ? (
                    <Badge variant="default" size="sm">Disabled</Badge>
                  ) : isNoAuth ? (
                    <Badge variant="success" size="sm">Ready</Badge>
                  ) : connected > 0 ? (
                    <Badge variant="success" size="sm">
                      <Plug size={10} className="mr-1" />{connected} Connected
                    </Badge>
                  ) : error > 0 ? (
                    <Badge variant="danger" size="sm">
                      <AlertCircle size={10} className="mr-1" />
                      {error} Error{errorCode ? ` (${errorCode})` : ''}
                    </Badge>
                  ) : (
                    <span className="text-zinc-500">No connections</span>
                  )}
                  {errorTime && <span className="text-zinc-600">{errorTime}</span>}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {stats.total > 0 && (
                <div
                  className="opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle(allDisabled) }}
                >
                  <Toggle checked={!allDisabled} onChange={() => {}} />
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

// ── API Key Provider Card ────────────────────────────────────────────────────
function ApiKeyProviderCard({ providerId, provider, stats, authType = 'apikey', onToggle, onAddKey }) {
  const { connected, error, errorCode, errorTime, allDisabled } = stats

  const dotColors = {
    free: 'bg-emerald-500',
    oauth: 'bg-blue-500',
    apikey: 'bg-amber-500',
    cookie: 'bg-purple-500',
    compatible: 'bg-orange-500',
  }

  const isOpenaiCompatible = providerId.startsWith('openai-compatible-')
  const isAnthropicCompatible = providerId.startsWith('anthropic-compatible-')
  const effectiveAuthType = isOpenaiCompatible || isAnthropicCompatible ? 'compatible' : authType

  return (
    <Link to={`/providers/${providerId}`} className="group min-w-0">
      <Card className={`h-full hover:border-zinc-600/80 transition-all duration-150 hover:bg-zinc-800/20 cursor-pointer ${allDisabled ? 'opacity-50' : ''}`}>
        <CardContent className="p-4">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <ProviderLogo providerId={providerId} provider={provider} size={32} />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">{provider.name}</h3>
                <div className="flex min-w-0 items-center gap-1.5 text-xs flex-wrap mt-0.5">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotColors[effectiveAuthType] || 'bg-zinc-500'}`} />
                  {allDisabled ? (
                    <Badge variant="default" size="sm">Disabled</Badge>
                  ) : connected > 0 ? (
                    <Badge variant="success" size="sm">
                      <Plug size={10} className="mr-1" />{connected} Connected
                    </Badge>
                  ) : error > 0 ? (
                    <Badge variant="danger" size="sm">
                      <AlertCircle size={10} className="mr-1" />
                      {error} Error{errorCode ? ` (${errorCode})` : ''}
                    </Badge>
                  ) : stats.total > 0 ? (
                    <span className="text-zinc-500">No active</span>
                  ) : (
                    <span className="text-zinc-500">No connections</span>
                  )}
                  {provider.apiType && (
                    <Badge variant="default" size="sm">
                      {provider.apiType === 'responses' ? 'Responses' : 'Chat'}
                    </Badge>
                  )}
                  {errorTime && <span className="text-zinc-600">{errorTime}</span>}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {stats.total > 0 && (
                <div
                  className="opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle(allDisabled) }}
                >
                  <Toggle checked={!allDisabled} onChange={() => {}} />
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

// ── Cookie Provider Card ─────────────────────────────────────────────────────
function CookieProviderCard({ providerId, provider, stats, onToggle, onAddKey }) {
  const { connected, error, errorCode, errorTime, allDisabled } = stats

  return (
    <Link to={`/providers/${providerId}`} className="group min-w-0">
      <Card className={`h-full hover:border-zinc-600/80 transition-all duration-150 hover:bg-zinc-800/20 cursor-pointer ${allDisabled ? 'opacity-50' : ''}`}>
        <CardContent className="p-4">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <ProviderLogo providerId={providerId} provider={provider} size={32} />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">{provider.name}</h3>
                <div className="flex min-w-0 items-center gap-1.5 text-xs flex-wrap mt-0.5">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-purple-500" />
                  {allDisabled ? (
                    <Badge variant="default" size="sm">Disabled</Badge>
                  ) : connected > 0 ? (
                    <Badge variant="success" size="sm">
                      <Plug size={10} className="mr-1" />{connected} Connected
                    </Badge>
                  ) : error > 0 ? (
                    <Badge variant="danger" size="sm">
                      <AlertCircle size={10} className="mr-1" />
                      {error} Error{errorCode ? ` (${errorCode})` : ''}
                    </Badge>
                  ) : (
                    <span className="text-zinc-500">No connections</span>
                  )}
                  <Badge variant="default" size="sm">Cookie</Badge>
                  {errorTime && <span className="text-zinc-600">{errorTime}</span>}
                </div>
                {provider.authHint && (
                  <p className="text-[11px] text-zinc-500 mt-1 truncate" title={provider.authHint}>
                    {provider.authHint}
                  </p>
                )}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {stats.total > 0 && (
                <div
                  className="opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle(allDisabled) }}
                >
                  <Toggle checked={!allDisabled} onChange={() => {}} />
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}

// ── Add API Key Modal (for OAuth/free providers that need keys) ──────────────
function AddApiKeyModal({ isOpen, providerKey, onClose, onCreated }) {
  const [apiKey, setApiKey] = useState('')
  const [connectionName, setConnectionName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [azureData, setAzureData] = useState({ azureEndpoint: '', apiVersion: '2024-10-01-preview', deployment: '', organization: '' })
  const [cloudflareData, setCloudflareData] = useState({ accountId: '' })
  const info = useCatalogStore((s) => s.providers[providerKey])
  const isAzure = providerKey === 'azure'
  const isCloudflareAi = providerKey === 'cloudflare-ai'

  useEffect(() => {
    if (isOpen) {
      setApiKey('')
      setConnectionName('')
      setCreateError('')
      setAzureData({ azureEndpoint: '', apiVersion: '2024-10-01-preview', deployment: '', organization: '' })
      setCloudflareData({ accountId: '' })
    }
  }, [isOpen])

  const handleCreate = async () => {
    if (!providerKey || !apiKey.trim()) return
    setCreating(true)
    try {
      const payload = {
        provider: providerKey,
        apiKey: apiKey.trim(),
        name: connectionName.trim() || null,
        auth_type: 'apikey',
        priority: 1,
      }
      if (isAzure) {
        payload.provider_specific_data = {
          azureEndpoint: azureData.azureEndpoint,
          apiVersion: azureData.apiVersion,
          deployment: azureData.deployment,
          organization: azureData.organization,
        }
      }
      if (isCloudflareAi) {
        payload.provider_specific_data = {
          accountId: cloudflareData.accountId,
        }
      }
      await providersApi.createProvider(payload)
      onCreated()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create connection'
      setCreateError(msg)
    } finally {
      setCreating(false)
    }
  }

  if (!info) return null

  const isSubmitDisabled = !apiKey.trim() || creating || (isAzure && !azureData.azureEndpoint.trim()) || (isCloudflareAi && !cloudflareData.accountId.trim())

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Add ${info.name} Connection`}>
      <div className="space-y-4">
        <Input
          label="Connection Name (optional)"
          placeholder="e.g. Production, Personal, Team"
          value={connectionName}
          onChange={(e) => setConnectionName(e.target.value)}
        />
        <Input
          label="API Key"
          type="password"
          placeholder={info.configFields?.find(f => f.key === 'apiKey')?.placeholder || 'sk-...'}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && apiKey.trim() && !creating) handleCreate()
          }}
        />
        {isAzure && (
          <div className="bg-zinc-800/30 p-4 rounded-lg border border-zinc-700 space-y-3">
            <h3 className="text-sm font-semibold text-zinc-200">Azure OpenAI Configuration</h3>
            <Input
              label="Azure Endpoint"
              placeholder="https://your-resource.openai.azure.com"
              value={azureData.azureEndpoint}
              onChange={(e) => setAzureData({ ...azureData, azureEndpoint: e.target.value })}
            />
            <Input
              label="API Version"
              placeholder="2024-10-01-preview"
              value={azureData.apiVersion}
              onChange={(e) => setAzureData({ ...azureData, apiVersion: e.target.value })}
            />
            <Input
              label="Deployment Name"
              placeholder="gpt-4"
              value={azureData.deployment}
              onChange={(e) => setAzureData({ ...azureData, deployment: e.target.value })}
            />
            <Input
              label="Organization (optional)"
              placeholder="Organization ID"
              value={azureData.organization}
              onChange={(e) => setAzureData({ ...azureData, organization: e.target.value })}
            />
          </div>
        )}
        {isCloudflareAi && (
          <div className="bg-zinc-800/30 p-4 rounded-lg border border-zinc-700 space-y-3">
            <h3 className="text-sm font-semibold text-zinc-200">Cloudflare Configuration</h3>
            <Input
              label="Account ID"
              placeholder="Your Cloudflare Account ID"
              value={cloudflareData.accountId}
              onChange={(e) => setCloudflareData({ ...cloudflareData, accountId: e.target.value })}
            />
          </div>
        )}
        <div className="flex justify-end gap-3 pt-2">
          {createError && (
            <p className="flex-1 text-sm text-red-400 self-center">{createError}</p>
          )}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleCreate} disabled={isSubmitDisabled}>
            {creating ? 'Adding...' : 'Add Connection'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Test Results View ────────────────────────────────────────────────────────
function ProviderTestResultsView({ results }) {
  if (results.error && !results.results) {
    return (
      <div className="text-center py-6">
        <XCircle size={32} className="mx-auto text-red-500 mb-2" />
        <p className="text-sm text-red-400">{results.error}</p>
      </div>
    )
  }

  const { summary, mode } = results
  const items = results.results || []
  const modeLabel = { oauth: 'OAuth', free: 'Free', apikey: 'API Key', provider: 'Provider', all: 'All' }[mode] || mode

  return (
    <div className="flex min-w-0 flex-col gap-3">
      {summary && (
        <div className="flex flex-wrap items-center gap-2 text-xs mb-1">
          <span className="text-zinc-500">{modeLabel} Test</span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-medium">
            {summary.passed} passed
          </span>
          {summary.failed > 0 && (
            <span className="px-2 py-0.5 rounded bg-red-500/15 text-red-400 font-medium">
              {summary.failed} failed
            </span>
          )}
          <span className="text-zinc-500 ml-auto">{summary.total} tested</span>
        </div>
      )}
      {items.map((r, i) => (
        <div key={r.connectionId || i} className="flex min-w-0 flex-wrap items-center gap-2 rounded-lg bg-zinc-800/50 px-3 py-2 text-xs">
          {r.valid ? (
            <CheckCircle size={16} className="text-emerald-500 shrink-0" />
          ) : (
            <XCircle size={16} className="text-red-500 shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <span className="block truncate font-medium text-zinc-200">{r.connectionName}</span>
            <span className="block truncate text-zinc-500">({r.provider})</span>
          </div>
          {r.latencyMs !== undefined && (
            <span className="shrink-0 text-zinc-500 font-mono tabular-nums">{r.latencyMs}ms</span>
          )}
          <span className={`shrink-0 text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
            r.valid ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
          }`}>
            {r.valid ? 'OK' : r.diagnosis?.type || 'ERROR'}
          </span>
        </div>
      ))}
      {items.length === 0 && (
        <div className="text-center py-4 text-zinc-500 text-sm">
          No active connections found for this group.
        </div>
      )}
    </div>
  )
}
