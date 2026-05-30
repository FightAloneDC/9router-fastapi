import { useState, useEffect, useCallback, useRef } from 'react'
import {
  CloudOff,
  RefreshCw,
  Settings,
  Server,
  AlertTriangle,
  ChevronDown,
  Timer,
  Pause,
  Play,
  Link,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import { quotaApi } from '../api/quota'

// --- Provider color map ---

const PROVIDER_COLORS = {
  openai: { bg: 'bg-emerald-600', text: 'text-white', label: 'OI' },
  anthropic: { bg: 'bg-amber-600', text: 'text-white', label: 'AN' },
  google: { bg: 'bg-blue-600', text: 'text-white', label: 'GO' },
  groq: { bg: 'bg-orange-600', text: 'text-white', label: 'GQ' },
  mistral: { bg: 'bg-sky-600', text: 'text-white', label: 'MI' },
  cohere: { bg: 'bg-purple-600', text: 'text-white', label: 'CO' },
  deepseek: { bg: 'bg-indigo-600', text: 'text-white', label: 'DS' },
  together: { bg: 'bg-teal-600', text: 'text-white', label: 'TG' },
  fireworks: { bg: 'bg-rose-600', text: 'text-white', label: 'FW' },
  xai: { bg: 'bg-zinc-500', text: 'text-white', label: 'XA' },
}

function getProviderStyle(provider) {
  const key = (provider || '').toLowerCase()
  if (PROVIDER_COLORS[key]) return PROVIDER_COLORS[key]
  const initials = (provider || '??').slice(0, 2).toUpperCase()
  return { bg: 'bg-zinc-600', text: 'text-white', label: initials }
}

// --- Quota helpers ---

function getQuotaColor(pct) {
  if (pct > 70) return 'green'
  if (pct > 30) return 'yellow'
  return 'red'
}

function getBarColors(color) {
  switch (color) {
    case 'green':
      return { bar: 'bg-emerald-500', track: 'bg-emerald-500/10', text: 'text-emerald-400', dot: 'bg-emerald-500' }
    case 'yellow':
      return { bar: 'bg-amber-500', track: 'bg-amber-500/10', text: 'text-amber-400', dot: 'bg-amber-500' }
    case 'red':
      return { bar: 'bg-red-500', track: 'bg-red-500/10', text: 'text-red-400', dot: 'bg-red-500' }
    default:
      return { bar: 'bg-zinc-500', track: 'bg-zinc-500/10', text: 'text-zinc-400', dot: 'bg-zinc-500' }
  }
}

function formatCountdown(resetAt) {
  if (!resetAt) return null
  const diffMs = new Date(resetAt) - new Date()
  if (diffMs <= 0) return 'now'
  const totalMin = Math.floor(diffMs / 60000)
  const d = Math.floor(totalMin / 1440)
  const h = Math.floor((totalMin % 1440) / 60)
  const m = totalMin % 60
  const parts = []
  if (d > 0) parts.push(`${d}d`)
  if (h > 0) parts.push(`${h}h`)
  parts.push(`${m}m`)
  return parts.join(' ')
}

function formatQuotaNum(n) {
  if (n == null) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  return n.toLocaleString('en-US')
}

// --- Skeleton ---

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="animate-pulse w-32 h-6 rounded-lg bg-zinc-800/60" />
        <div className="animate-pulse w-24 h-8 rounded-lg bg-zinc-800/60" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="animate-pulse rounded-xl bg-zinc-800/60 h-16" />
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="animate-pulse rounded-xl bg-zinc-800/60 h-40" />
        ))}
      </div>
    </div>
  )
}

// --- Empty states ---

function ErrorState({ message, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[30vh] text-center">
      <div className="w-12 h-12 rounded-xl bg-red-600/20 flex items-center justify-center mb-4">
        <AlertTriangle size={22} className="text-red-400" />
      </div>
      <h2 className="text-base font-semibold text-zinc-300 mb-1">Failed to load quota data</h2>
      <p className="text-xs text-zinc-500 max-w-md mb-3">{message}</p>
      <button
        onClick={onRetry}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 border border-zinc-700 text-xs text-zinc-300 hover:bg-zinc-700 transition-colors cursor-pointer"
      >
        <RefreshCw size={12} />
        Retry
      </button>
    </div>
  )
}

function EmptyConnectionsState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[30vh] text-center">
      <div className="w-12 h-12 rounded-xl bg-zinc-800 flex items-center justify-center mb-4">
        <CloudOff size={22} className="text-zinc-500" />
      </div>
      <h2 className="text-base font-semibold text-zinc-300 mb-1">No Providers Connected</h2>
      <p className="text-xs text-zinc-500 max-w-md mb-4">
        Connect a provider to start tracking API usage quotas and limits.
      </p>
      <a
        href="/providers"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors"
      >
        <Link size={12} />
        Connect a Provider
      </a>
    </div>
  )
}

function EmptyQuotaState() {
  return (
    <div className="flex flex-col items-center justify-center py-6 text-center">
      <CloudOff size={18} className="text-zinc-600 mb-2" />
      <p className="text-xs text-zinc-500">No quota data available</p>
    </div>
  )
}

// --- Quota bar (compact) ---

function QuotaBar({ quota }) {
  const pct = quota.remaining_percentage ?? 0
  const usedPct = Math.min(100, Math.max(0, 100 - pct))
  const color = getQuotaColor(pct)
  const colors = getBarColors(color)
  const countdown = formatCountdown(quota.reset_at)

  return (
    <div className="space-y-1">
      {/* Single row: dot + name + used/total + pct + countdown */}
      <div className="flex items-center gap-1.5 text-[11px]">
        <span className={`w-1.5 h-1.5 rounded-full ${colors.dot} shrink-0`} />
        <span className="text-zinc-300 font-medium truncate flex-1 min-w-0">{quota.name}</span>
        <span className="text-zinc-500 whitespace-nowrap tabular-nums">
          {formatQuotaNum(quota.used)}/{formatQuotaNum(quota.total)}
        </span>
        <span className={`${colors.text} whitespace-nowrap tabular-nums font-medium`}>
          {pct.toFixed(0)}%
        </span>
        {countdown && (
          <span className="text-zinc-600 whitespace-nowrap flex items-center gap-0.5">
            <Timer size={9} />
            {countdown}
          </span>
        )}
      </div>

      {/* Slim progress bar */}
      <div className={`w-full h-1.5 rounded-full ${colors.track}`}>
        <div
          className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
          style={{ width: `${usedPct}%` }}
        />
      </div>
    </div>
  )
}

// --- Provider card (compact) ---

function ProviderQuotaCard({ provider, onRefresh, isRefreshing }) {
  const style = getProviderStyle(provider.provider)
  const hasQuotas = provider.quotas && provider.quotas.length > 0
  const lowCount = hasQuotas
    ? provider.quotas.filter((q) => (q.remaining_percentage ?? 100) <= 30).length
    : 0

  return (
    <Card className="hover:border-zinc-600/50 transition-colors">
      <CardHeader className="px-4 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div
              className={`w-8 h-8 rounded-full ${style.bg} ${style.text} flex items-center justify-center text-[10px] font-bold shrink-0`}
            >
              {style.label}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <h3 className="text-sm font-semibold text-zinc-100 truncate">
                  {provider.name || provider.provider}
                </h3>
                {provider.plan && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-blue-600/20 text-blue-400 shrink-0">
                    {provider.plan}
                  </span>
                )}
                {lowCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-red-600/20 text-red-400 shrink-0">
                    {lowCount} low
                  </span>
                )}
              </div>
              <p className="text-[11px] text-zinc-500 truncate">{provider.provider}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <span className={`w-1.5 h-1.5 rounded-full ${provider.is_active ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
            <button
              onClick={() => onRefresh(provider.id)}
              disabled={isRefreshing}
              className="p-1 rounded-md hover:bg-zinc-800 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh quota data"
            >
              <RefreshCw size={12} className={`text-zinc-400 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-4 py-3">
        {hasQuotas ? (
          <div className="space-y-2.5">
            {provider.quotas.map((quota, idx) => (
              <QuotaBar key={quota.name || idx} quota={quota} />
            ))}
          </div>
        ) : (
          <EmptyQuotaState />
        )}
      </CardContent>
    </Card>
  )
}

// --- Summary stat (compact) ---

function SummaryStat({ icon: Icon, label, value, bgClass, textClass }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 px-4 py-3">
        <div className={`p-2 rounded-lg ${bgClass}`}>
          <Icon size={16} className={textClass} />
        </div>
        <div>
          <p className="text-[11px] text-zinc-500">{label}</p>
          <p className="text-lg font-bold text-zinc-100 tabular-nums">{value}</p>
        </div>
      </CardContent>
    </Card>
  )
}

// --- Main Page ---

export default function QuotaTrackerPage() {
  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [countdown, setCountdown] = useState(60)
  const [providerFilter, setProviderFilter] = useState('all')
  const [refreshingId, setRefreshingId] = useState(null)
  const [tabVisible, setTabVisible] = useState(true)

  const intervalRef = useRef(null)
  const countdownRef = useRef(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await quotaApi.getQuotaData()
      setProviders(res.data || [])
      setError(null)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  useEffect(() => {
    const handleVisibility = () => setTabVisible(!document.hidden)
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (countdownRef.current) clearInterval(countdownRef.current)

    if (autoRefresh && tabVisible) {
      setCountdown(60)
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => (prev <= 1 ? 60 : prev - 1))
      }, 1000)
      intervalRef.current = setInterval(() => {
        fetchData()
        setCountdown(60)
      }, 60000)
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [autoRefresh, tabVisible, fetchData])

  const handleRefreshProvider = async (id) => {
    setRefreshingId(id)
    try { await fetchData() } finally { setRefreshingId(null) }
  }

  if (loading) return <LoadingSkeleton />
  if (error && providers.length === 0) return <ErrorState message={error} onRetry={fetchData} />
  if (providers.length === 0) return <EmptyConnectionsState />

  const totalProviders = providers.length
  const activeWithLimits = providers.filter((p) => p.is_active && p.quotas?.length > 0).length
  const lowQuotas = providers.reduce((acc, p) => {
    if (!p.quotas) return acc
    return acc + p.quotas.filter((q) => (q.remaining_percentage ?? 100) <= 30).length
  }, 0)

  const providerTypes = [...new Set(providers.map((p) => p.provider))].sort()
  const filteredProviders = providerFilter === 'all'
    ? providers
    : providers.filter((p) => p.provider === providerFilter)

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-semibold text-zinc-100">Quota Tracker</h1>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-colors cursor-pointer ${
              autoRefresh
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
                : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
            }`}
          >
            {autoRefresh ? (
              <><Pause size={11} /> Auto ({countdown}s)</>
            ) : (
              <><Play size={11} /> Paused</>
            )}
          </button>

          <button
            onClick={() => { fetchData(); setCountdown(60) }}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700 hover:bg-zinc-700 hover:text-zinc-200 transition-colors cursor-pointer"
          >
            <RefreshCw size={11} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SummaryStat icon={Server} label="Total Providers" value={totalProviders} bgClass="bg-blue-600/20" textClass="text-blue-400" />
        <SummaryStat icon={Settings} label="Active with Limits" value={activeWithLimits} bgClass="bg-emerald-600/20" textClass="text-emerald-400" />
        <SummaryStat icon={AlertTriangle} label="Low Quotas" value={lowQuotas} bgClass={lowQuotas > 0 ? 'bg-red-600/20' : 'bg-zinc-800'} textClass={lowQuotas > 0 ? 'text-red-400' : 'text-zinc-500'} />
      </div>

      {/* Provider filter */}
      {providerTypes.length > 1 && (
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-zinc-500">Filter:</span>
          <div className="relative">
            <select
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
              className="appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 pr-7 text-[11px] text-zinc-300 focus:outline-none focus:border-zinc-600 cursor-pointer"
            >
              <option value="all">All Providers</option>
              {providerTypes.map((type) => (
                <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
              ))}
            </select>
            <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
          </div>
        </div>
      )}

      {/* Provider cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filteredProviders.map((provider) => (
          <ProviderQuotaCard
            key={provider.id}
            provider={provider}
            onRefresh={handleRefreshProvider}
            isRefreshing={refreshingId === provider.id}
          />
        ))}
      </div>

      {filteredProviders.length === 0 && (
        <div className="text-center py-8">
          <p className="text-xs text-zinc-500">No providers match the selected filter.</p>
        </div>
      )}
    </div>
  )
}
