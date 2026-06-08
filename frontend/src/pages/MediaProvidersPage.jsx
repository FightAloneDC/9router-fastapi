import { useState, useEffect, useCallback } from 'react'

// Provider logo with text fallback
function ProviderLogo({ providerId, provider, size = 40 }) {
  const [imgError, setImgError] = useState(false)
  const src = `/providers/${providerId}.png`
  if (imgError) {
    return (
      <div
        className="shrink-0 rounded-lg flex items-center justify-center text-sm font-bold"
        style={{ width: size, height: size, backgroundColor: (provider.color || '#888') + '15', color: provider.color || '#888' }}
      >
        {provider.textIcon || provider.icon || providerId.slice(0, 2).toUpperCase()}
      </div>
    )
  }
  return (
    <img src={src} alt={provider.name || providerId} width={size} height={size}
      className="shrink-0 rounded-lg object-contain" style={{ width: size, height: size }}
      onError={() => setImgError(true)}
    />
  )
}
import { useParams, useNavigate } from 'react-router-dom'
import { Binary, Volume2, Mic, Search, Globe, Image, Eye, Video, Music, ChevronRight } from 'lucide-react'
import useCatalogStore from '../stores/catalogStore'
import { providersApi } from '../api/providers'
import Card, { CardContent } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Loading from '../components/ui/Loading'

// Icon map for media kinds
const KIND_ICONS = {
  embedding: Binary,
  tts: Volume2,
  stt: Mic,
  webSearch: Search,
  webFetch: Globe,
  image: Image,
  imageToText: Eye,
  video: Video,
  music: Music,
}

function getEffectiveStatus(conn) {
  const data = conn.data || {}
  const isCooldown = Object.entries(data).some(
    ([k, v]) => k.startsWith('modelLock_') && v && new Date(v).getTime() > Date.now()
  )
  return conn.test_status === 'unavailable' && !isCooldown ? 'active' : conn.test_status
}

function ProviderCard({ provider, connections, kind }) {
  const navigate = useNavigate()
  const providerConns = connections.filter((c) => c.provider === provider.id)
  const connected = providerConns.filter((c) => {
    const s = getEffectiveStatus(c)
    return s === 'active' || s === 'success'
  }).length
  const errors = providerConns.filter((c) => {
    const s = getEffectiveStatus(c)
    return s === 'error' || s === 'expired' || s === 'unavailable'
  }).length
  const total = providerConns.length
  const allDisabled = total > 0 && providerConns.every((c) => !c.is_active)

  const renderStatus = () => {
    if (allDisabled) return <Badge variant="default" size="sm">Disabled</Badge>
    if (total === 0) return <span className="text-xs text-zinc-500">No connections</span>
    return (
      <div className="flex items-center gap-1.5">
        {connected > 0 && <Badge variant="success" size="sm">{connected} Active</Badge>}
        {errors > 0 && <Badge variant="error" size="sm">{errors} Error</Badge>}
        {connected === 0 && errors === 0 && <Badge variant="default" size="sm">{total} Added</Badge>}
      </div>
    )
  }

  return (
    <div
      onClick={() => navigate(`/media-providers/${kind}/${provider.id}`)}
      className="group cursor-pointer"
    >
      <Card className={`h-full hover:border-zinc-600/80 transition-all duration-150 hover:bg-zinc-800/20 cursor-pointer ${allDisabled ? 'opacity-50' : ''}`}>
        <CardContent className="p-4">
          <div className="flex min-w-0 items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <ProviderLogo providerId={provider.id} provider={provider} size={40} />
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">{provider.name}</h3>
                <div className="mt-0.5">{renderStatus()}</div>
              </div>
            </div>
            <ChevronRight size={16} className="text-zinc-600 group-hover:text-zinc-400 transition-colors shrink-0" />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function KindSection({ kind, providers, connections }) {
  const KindIcon = KIND_ICONS[kind.id] || Image

  if (!providers || providers.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-3">
          <KindIcon size={16} className="text-blue-400" />
          <h2 className="text-sm font-semibold text-zinc-200">{kind.label}</h2>
        </div>
        <div className="text-center py-8 border border-dashed border-zinc-700 rounded-xl text-zinc-500 text-sm">
          No providers support <strong>{kind.label}</strong> yet.
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <KindIcon size={16} className="text-blue-400" />
        <h2 className="text-sm font-semibold text-zinc-200">{kind.label}</h2>
        <span className="text-xs text-zinc-500">({providers.length} providers)</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {providers.map((provider) => (
          <ProviderCard
            key={provider.id}
            provider={provider}
            connections={connections}
            kind={kind.id}
          />
        ))}
      </div>
    </div>
  )
}

export default function MediaProvidersPage() {
  const { kind: urlKind } = useParams()
  const navigate = useNavigate()
  const activeKind = urlKind || 'embedding'
  const [connections, setConnections] = useState([])
  const [tabProviders, setTabProviders] = useState({})  // { [kind]: providers[] }
  const [loading, setLoading] = useState(true)
  const [tabLoading, setTabLoading] = useState(false)

  // Fetch connections (for status display) — once on mount
  useEffect(() => {
    providersApi.getProviders()
      .then((res) => setConnections(res.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // Fetch providers for active tab from API
  const fetchTabProviders = useCallback(async (kind) => {
    setTabLoading(true)
    try {
      if (kind === 'webSearch' || kind === 'webFetch') {
        // Web tab: fetch both webSearch and webFetch
        const [searchRes, fetchRes] = await Promise.all([
          providersApi.getMediaProviders('webSearch'),
          providersApi.getMediaProviders('webFetch'),
        ])
        setTabProviders((prev) => ({
          ...prev,
          webSearch: searchRes.data || [],
          webFetch: fetchRes.data || [],
        }))
      } else {
        const res = await providersApi.getMediaProviders(kind)
        setTabProviders((prev) => ({
          ...prev,
          [kind]: res.data || [],
        }))
      }
    } catch {
      // Keep existing data on error
    } finally {
      setTabLoading(false)
    }
  }, [])

  // When active kind changes, fetch providers for that tab
  useEffect(() => {
    if (activeKind) {
      fetchTabProviders(activeKind)
    }
  }, [activeKind, fetchTabProviders])

  // Redirect /media-providers to default tab
  useEffect(() => {
    if (!urlKind) {
      navigate('/media-providers/embedding', { replace: true })
    }
  }, [urlKind, navigate])

  if (loading) return <Loading />

  // Tab items for the tab bar
  const tabs = [
    { id: 'embedding', label: 'Embedding' },
    { id: 'tts', label: 'TTS' },
    { id: 'stt', label: 'STT' },
    { id: 'webSearch', label: 'Web' },
    { id: 'image', label: 'Images' },
  ]

  const handleTabClick = (tabId) => {
    navigate(`/media-providers/${tabId}`)
  }

  // Render content for active tab
  const renderContent = () => {
    if (tabLoading) return <Loading />

    if (activeKind === 'webSearch' || activeKind === 'webFetch') {
      // Web tab shows both search and fetch
      const searchConfig = useCatalogStore.getState().mediaKinds.find((k) => k.id === 'webSearch')
      const fetchConfig = useCatalogStore.getState().mediaKinds.find((k) => k.id === 'webFetch')
      return (
        <div className="space-y-6">
          {searchConfig && (
            <KindSection
              kind={searchConfig}
              providers={tabProviders.webSearch || []}
              connections={connections}
            />
          )}
          {fetchConfig && (
            <>
              <div className="border-t border-zinc-800" />
              <KindSection
                kind={fetchConfig}
                providers={tabProviders.webFetch || []}
                connections={connections}
              />
            </>
          )}
        </div>
      )
    }

    const kindConfig = useCatalogStore.getState().mediaKinds.find((k) => k.id === activeKind)
    if (!kindConfig) {
      return (
        <div className="text-center py-12 text-zinc-500">
          Kind not found.
        </div>
      )
    }

    return (
      <KindSection
        kind={kindConfig}
        providers={tabProviders[activeKind] || []}
        connections={connections}
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-zinc-800 pb-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeKind === tab.id || (tab.id === 'webSearch' && (activeKind === 'webSearch' || activeKind === 'webFetch'))
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {renderContent()}
    </div>
  )
}
