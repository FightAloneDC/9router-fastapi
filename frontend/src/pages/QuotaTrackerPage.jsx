import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
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
  Search,
  X,
  MoreVertical,
  Edit2,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Zap,
  ZapOff,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import { quotaApi } from '../api/quota'
import { providersApi } from '../api/providers'

// --- Provider logo fallback ---

function ProviderLogo({ providerId, providerName, size = 32 }) {
  const [imgError, setImgError] = useState(false)
  const src = `/providers/${providerId}.png`

  if (imgError) {
    const initials = (providerName || providerId || '??').slice(0, 2).toUpperCase()
    return (
      <div
        className="rounded-lg bg-zinc-700 flex items-center justify-center text-[10px] font-bold text-zinc-300 shrink-0"
        style={{ width: size, height: size }}
      >
        {initials}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={providerName || providerId}
      width={size}
      height={size}
      className="rounded-lg object-contain shrink-0"
      onError={() => setImgError(true)}
    />
  )
}

// --- Quota helpers ---

function getQuotaColor(pct) {
  if (pct > 70) return 'green'
  if (pct >= 30) return 'yellow'
  return 'red'
}

function getEmoji(pct) {
  if (pct > 70) return '🟢'
  if (pct >= 30) return '🟡'
  return '🔴'
}

function getBarColors(color) {
  switch (color) {
    case 'green':
      return {
        bar: 'bg-emerald-500',
        track: 'bg-emerald-500/10',
        text: 'text-emerald-400',
        dot: 'bg-emerald-500',
      }
    case 'yellow':
      return {
        bar: 'bg-amber-500',
        track: 'bg-amber-500/10',
        text: 'text-amber-400',
        dot: 'bg-amber-500',
      }
    case 'red':
      return {
        bar: 'bg-red-500',
        track: 'bg-red-500/10',
        text: 'text-red-400',
        dot: 'bg-red-500',
      }
    default:
      return {
        bar: 'bg-zinc-500',
        track: 'bg-zinc-500/10',
        text: 'text-zinc-400',
        dot: 'bg-zinc-500',
      }
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

function formatResetTimeDisplay(resetAt) {
  if (!resetAt) return null
  try {
    const date = new Date(resetAt)
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    const dayAfter = new Date(tomorrow)
    dayAfter.setDate(dayAfter.getDate() + 1)

    const timeStr = date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })

    if (date >= today && date < tomorrow) return `Today, ${timeStr}`
    if (date >= tomorrow && date < dayAfter) return `Tomorrow, ${timeStr}`
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }) + `, ${timeStr}`
  } catch {
    return null
  }
}

function formatQuotaNum(n) {
  if (n == null) return '0'
  if (n >= 1_000_000)
    return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000)
    return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  return n.toLocaleString('en-US')
}

function getLowCount(quotas) {
  if (!quotas) return 0
  return quotas.filter((q) => (q.remaining_percentage ?? 100) <= 30).length
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
          <div
            key={i}
            className="animate-pulse rounded-xl bg-zinc-800/60 h-16"
          />
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="animate-pulse rounded-xl bg-zinc-800/60 h-48"
          />
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
      <h2 className="text-base font-semibold text-zinc-300 mb-1">
        Failed to load quota data
      </h2>
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
      <div className="w-14 h-14 rounded-2xl bg-zinc-800 flex items-center justify-center mb-4">
        <CloudOff size={24} className="text-zinc-500" />
      </div>
      <h2 className="text-base font-semibold text-zinc-200 mb-1">
        No Providers Connected
      </h2>
      <p className="text-xs text-zinc-500 max-w-sm mb-1">
        Connect a provider to start tracking API usage quotas and limits.
      </p>
      <p className="text-[10px] text-zinc-600 max-w-sm mb-4">
        OAuth providers (Claude, Codex, etc.) will show quota data automatically once connected.
      </p>
      <a
        href="/providers"
        className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 transition-colors"
      >
        <Link size={12} />
        Connect a Provider
      </a>
    </div>
  )
}

// --- Quota table row (per quota item) ---

function QuotaRow({ quota }) {
  const pct = quota.remaining_percentage ?? 0
  const usedPct = Math.min(100, Math.max(0, 100 - pct))
  const color = getQuotaColor(pct)
  const colors = getBarColors(color)
  const emoji = getEmoji(pct)
  const countdown = formatCountdown(quota.reset_at)
  const resetDisplay = formatResetTimeDisplay(quota.reset_at)

  return (
    <tr className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/20 transition-colors">
      {/* Emoji + Name */}
      <td className="py-1.5 px-2 w-[30%]">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-[10px] shrink-0">{emoji}</span>
          <span className="text-[11px] font-medium text-zinc-300 truncate">
            {quota.name}
          </span>
        </div>
      </td>

      {/* Progress bar */}
      <td className="py-1.5 px-2 w-[40%]">
        <div className="space-y-1">
          <div className="h-1.5 rounded-full overflow-hidden bg-zinc-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
              style={{ width: `${usedPct}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-zinc-500">
              {formatQuotaNum(quota.used)} /{' '}
              {quota.total > 0 ? formatQuotaNum(quota.total) : '∞'}
            </span>
            <span className={`font-medium ${colors.text}`}>
              {pct.toFixed(0)}%
            </span>
          </div>
        </div>
      </td>

      {/* Reset time */}
      <td className="py-1.5 px-2 w-[30%] text-right">
        {countdown || resetDisplay ? (
          <div className="space-y-0.5">
            {countdown && (
              <div className="text-[11px] text-zinc-300 font-medium flex items-center justify-end gap-0.5">
                <Timer size={9} className="text-zinc-500" />
                in {countdown}
              </div>
            )}
            {resetDisplay && (
              <div className="text-[10px] text-zinc-600">
                {resetDisplay}
              </div>
            )}
          </div>
        ) : (
          <span className="text-[10px] text-zinc-600 italic">N/A</span>
        )}
      </td>
    </tr>
  )
}

// --- Confirm modal ---

function ConfirmModal({ title, message, confirmLabel, confirmClass, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 max-w-sm w-full mx-4 shadow-2xl">
        <h3 className="text-sm font-semibold text-zinc-100 mb-2">{title}</h3>
        <p className="text-xs text-zinc-400 mb-5">{message}</p>
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors cursor-pointer ${confirmClass || 'bg-red-600 text-white hover:bg-red-700'}`}
          >
            {confirmLabel || 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

// --- Edit name modal ---

function EditNameModal({ currentName, onSave, onCancel }) {
  const [name, setName] = useState(currentName || '')

  const handleSubmit = (e) => {
    e.preventDefault()
    onSave(name.trim())
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 max-w-sm w-full mx-4 shadow-2xl"
      >
        <h3 className="text-sm font-semibold text-zinc-100 mb-3">Edit Connection Name</h3>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Connection name"
          autoFocus
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 mb-4"
        />
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-zinc-800 text-zinc-300 border border-zinc-700 hover:bg-zinc-700 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
          >
            Save
          </button>
        </div>
      </form>
    </div>
  )
}

// --- Dropdown menu ---

function CardMenu({ provider, onToggle, onEdit, onDelete }) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen(!open)}
        className="p-1 rounded-md hover:bg-zinc-800 transition-colors cursor-pointer"
        title="Actions"
      >
        <MoreVertical size={14} className="text-zinc-500" />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-44 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl z-20 py-1">
          <button
            onClick={() => { onToggle(); setOpen(false) }}
            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            {provider.is_active ? (
              <><ToggleLeft size={13} className="text-amber-400" /> Disable</>
            ) : (
              <><ToggleRight size={13} className="text-emerald-400" /> Enable</>
            )}
          </button>
          <button
            onClick={() => { onEdit(); setOpen(false) }}
            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-zinc-300 hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <Edit2 size={13} className="text-blue-400" /> Edit Name
          </button>
          <div className="border-t border-zinc-800 my-1" />
          <button
            onClick={() => { onDelete(); setOpen(false) }}
            className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-red-400 hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <Trash2 size={13} /> Delete
          </button>
        </div>
      )}
    </div>
  )
}

// --- Provider card (compact, 2-column layout) ---

function ProviderQuotaCard({ provider, onRefresh, isRefreshing, isLoadingUsage, onToggle, onEdit, onDelete }) {
  const hasQuotas = provider.quotas && provider.quotas.length > 0
  const lowCount = getLowCount(provider.quotas)

  return (
    <Card className="hover:border-zinc-600/50 transition-colors">
      <CardHeader className="px-4 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <ProviderLogo
              providerId={provider.provider}
              providerName={provider.name}
              size={32}
            />
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
              <p className="text-[11px] text-zinc-500 truncate">
                {provider.provider}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <span
              className={`w-2 h-2 rounded-full ${
                provider.is_active ? 'bg-emerald-500' : 'bg-zinc-600'
              }`}
              title={provider.is_active ? 'Active' : 'Inactive'}
            />
            <button
              onClick={() => onRefresh(provider.id)}
              disabled={isRefreshing}
              className="p-1 rounded-md hover:bg-zinc-800 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh quota data"
            >
              <RefreshCw
                size={12}
                className={`text-zinc-400 ${
                  isRefreshing ? 'animate-spin' : ''
                }`}
              />
            </button>
            <CardMenu
              provider={provider}
              onToggle={() => onToggle(provider.id, !provider.is_active)}
              onEdit={() => onEdit(provider)}
              onDelete={() => onDelete(provider)}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="px-0 py-0">
        {isLoadingUsage ? (
          <div className="flex items-center justify-center py-6 gap-2">
            <RefreshCw size={14} className="text-zinc-500 animate-spin" />
            <p className="text-xs text-zinc-500">Fetching usage…</p>
          </div>
        ) : hasQuotas ? (
          <table className="w-full table-fixed text-left">
            <thead>
              <tr className="border-b border-zinc-800/50 text-[9px] text-zinc-600 uppercase tracking-wider">
                <th className="py-1 px-2 font-normal w-[30%]">Quota</th>
                <th className="py-1 px-2 font-normal w-[40%]">Usage</th>
                <th className="py-1 px-2 font-normal w-[30%] text-right">
                  Resets
                </th>
              </tr>
            </thead>
            <tbody>
              {provider.quotas.map((quota, idx) => (
                <QuotaRow key={quota.name || idx} quota={quota} />
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <CloudOff size={18} className="text-zinc-600 mb-2" />
            <p className="text-xs text-zinc-500">
              {provider.usage_message || 'No quota data available'}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- Summary stat ---

function SummaryStat({ icon: Icon, label, value, bgClass, textClass }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 px-4 py-3">
        <div className={`p-2 rounded-lg ${bgClass}`}>
          <Icon size={16} className={textClass} />
        </div>
        <div>
          <p className="text-[11px] text-zinc-500">{label}</p>
          <p className="text-lg font-bold text-zinc-100 tabular-nums">
            {value}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

// --- Filter dropdown ---

function FilterDropdown({ label, value, options, onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-zinc-600">{label}:</span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="appearance-none bg-zinc-800/80 border border-zinc-700/50 rounded-md px-2 py-1 pr-6 text-[11px] text-zinc-300 focus:outline-none focus:border-zinc-600 cursor-pointer"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown
          size={10}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
        />
      </div>
    </div>
  )
}

// --- Sort options ---

const SORT_OPTIONS = [
  { value: 'default', label: 'Default order' },
  { value: 'remaining-asc', label: '% quota: low → high' },
  { value: 'remaining-desc', label: '% quota: high → low' },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'All status' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
]

const REFRESH_INTERVALS = [
  { value: 30, label: '30s' },
  { value: 60, label: '60s' },
  { value: 180, label: '180s' },
]

const PAGE_SIZE_OPTIONS = [10, 20, 50]

// --- localStorage cache helpers ---

const QUOTA_CACHE_KEY = 'quotaCacheData'

function getQuotaCache() {
  try {
    const cached = localStorage.getItem(QUOTA_CACHE_KEY)
    return cached ? JSON.parse(cached) : {}
  } catch {
    return {}
  }
}

function setQuotaCache(data) {
  try {
    localStorage.setItem(QUOTA_CACHE_KEY, JSON.stringify({
      data,
      timestamp: Date.now(),
    }))
  } catch {
    // ignore
  }
}

function getCachedQuotaData() {
  try {
    const cached = getQuotaCache()
    if (!cached.data || !cached.timestamp) return null
    // Cache valid for 5 minutes
    if (Date.now() - cached.timestamp > 5 * 60 * 1000) return null
    return cached.data
  } catch {
    return null
  }
}

// --- Main Page ---

export default function QuotaTrackerPage() {
  const [providers, setProviders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(60)
  const [countdown, setCountdown] = useState(60)
  const [pageSize, setPageSize] = useState(20)
  const [currentPage, setCurrentPage] = useState(1)
  const [providerFilter, setProviderFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortMode, setSortMode] = useState('default')
  const [expiringFirst, setExpiringFirst] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [refreshingId, setRefreshingId] = useState(null)
  const [loadingUsage, setLoadingUsage] = useState(new Set())
  const [tabVisible, setTabVisible] = useState(true)
  const [editingProvider, setEditingProvider] = useState(null)
  const [confirmAction, setConfirmAction] = useState(null)

  const intervalRef = useRef(null)
  const countdownRef = useRef(null)

  const fetchUsageForConnection = useCallback(
    async (connId, force = false) => {
      try {
        const res = await quotaApi.getUsage(connId, force)
        const usage = res.data
        if (!usage) return
        setProviders((prev) =>
          prev.map((p) =>
            p.id === connId
              ? {
                  ...p,
                  quotas: (usage.quotas || []).map((q) => ({
                    name: q.name,
                    used: q.used,
                    total: q.total,
                    remaining_percentage:
                      q.remaining_percentage ?? 0,
                    reset_at: q.reset_at || null,
                  })),
                  plan: usage.plan || p.plan,
                  usage_message: usage.message || null,
                }
              : p
          )
        )
      } catch {
        // Per-connection failure — leave quotas empty
      } finally {
        setLoadingUsage((prev) => {
          const next = new Set(prev)
          next.delete(connId)
          return next
        })
      }
    },
    []
  )

  const fetchAllUsage = useCallback(
    async (connections) => {
      const ids = connections
        .filter((c) => c.is_active)
        .map((c) => c.id)
      if (ids.length === 0) return

      setLoadingUsage(new Set(ids))

      // Fetch in batches of 5 to avoid overwhelming backend
      const batchSize = 5
      for (let i = 0; i < ids.length; i += batchSize) {
        const batch = ids.slice(i, i + batchSize)
        await Promise.all(
          batch.map((id) => fetchUsageForConnection(id))
        )
      }
    },
    [fetchUsageForConnection]
  )

  const fetchData = useCallback(async (useCache = false) => {
    try {
      // Try cache first on initial load
      if (useCache) {
        const cached = getCachedQuotaData()
        if (cached) {
          setProviders(cached)
          setLoading(false)
          // Still fetch fresh data in background
        }
      }

      const res = await quotaApi.getQuotaData()
      const data = res.data || []
      setProviders(data)
      setError(null)

      // Fetch real usage data per connection
      await fetchAllUsage(data)

      // Cache after usage is populated
      setProviders((current) => {
        setQuotaCache(current)
        return current
      })
    } catch (err) {
      // If fetch fails but we have cache, use it
      if (useCache) {
        const cached = getCachedQuotaData()
        if (cached) {
          setProviders(cached)
          setError(null)
          setLoading(false)
          return
        }
      }
      setError(
        err.response?.data?.detail || err.message || 'Unknown error'
      )
    } finally {
      setLoading(false)
    }
  }, [fetchAllUsage])

  useEffect(() => {
    fetchData(true)
  }, [fetchData])

  useEffect(() => {
    const handleVisibility = () => setTabVisible(!document.hidden)
    document.addEventListener('visibilitychange', handleVisibility)
    return () =>
      document.removeEventListener('visibilitychange', handleVisibility)
  }, [])

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (countdownRef.current) clearInterval(countdownRef.current)

    if (autoRefresh && tabVisible) {
      setCountdown(refreshInterval)
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => (prev <= 1 ? refreshInterval : prev - 1))
      }, 1000)
      intervalRef.current = setInterval(() => {
        fetchData()
        setCountdown(refreshInterval)
      }, refreshInterval * 1000)
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (countdownRef.current) clearInterval(countdownRef.current)
    }
  }, [autoRefresh, tabVisible, fetchData, refreshInterval])

  const handleRefreshProvider = async (id) => {
    setRefreshingId(id)
    setLoadingUsage((prev) => new Set(prev).add(id))
    try {
      // Manual refresh always polls the provider upstream
      await fetchUsageForConnection(id, true)
    } finally {
      setRefreshingId(null)
    }
  }

  const handleToggleActive = async (id, newActive) => {
    // Optimistic update
    setProviders((prev) =>
      prev.map((p) => (p.id === id ? { ...p, is_active: newActive } : p))
    )
    try {
      await providersApi.updateProvider(id, { is_active: newActive })
    } catch {
      // Rollback
      setProviders((prev) =>
        prev.map((p) => (p.id === id ? { ...p, is_active: !newActive } : p))
      )
    }
  }

  const handleEditName = async (newName) => {
    if (!editingProvider) return
    const id = editingProvider.id
    const oldName = editingProvider.name
    // Optimistic update
    setProviders((prev) =>
      prev.map((p) => (p.id === id ? { ...p, name: newName } : p))
    )
    setEditingProvider(null)
    try {
      await providersApi.updateProvider(id, { name: newName })
    } catch {
      // Rollback
      setProviders((prev) =>
        prev.map((p) => (p.id === id ? { ...p, name: oldName } : p))
      )
    }
  }

  const handleDelete = async () => {
    if (!confirmAction || confirmAction.type !== 'delete') return
    const id = confirmAction.provider.id
    const name = confirmAction.provider.name || confirmAction.provider.provider
    setConfirmAction(null)
    // Optimistic remove
    setProviders((prev) => prev.filter((p) => p.id !== id))
    try {
      await providersApi.deleteProvider(id)
    } catch {
      // Rollback - re-fetch
      fetchData()
    }
  }

  const handleBulkDisableDepleted = () => {
    const depleted = providers.filter(
      (p) =>
        p.is_active &&
        p.quotas?.some((q) => (q.remaining_percentage ?? 100) <= 5)
    )
    if (depleted.length === 0) return
    setConfirmAction({
      type: 'bulk-disable',
      count: depleted.length,
      ids: depleted.map((p) => p.id),
    })
  }

  const handleBulkDisableConfirm = async () => {
    if (!confirmAction || confirmAction.type !== 'bulk-disable') return
    const ids = confirmAction.ids
    setConfirmAction(null)
    // Optimistic update
    setProviders((prev) =>
      prev.map((p) => (ids.includes(p.id) ? { ...p, is_active: false } : p))
    )
    try {
      await Promise.all(
        ids.map((id) => providersApi.updateProvider(id, { is_active: false }))
      )
    } catch {
      fetchData()
    }
  }

  const handleBulkEnableAll = async () => {
    const inactive = providers.filter((p) => !p.is_active)
    if (inactive.length === 0) return
    const ids = inactive.map((p) => p.id)
    // Optimistic update
    setProviders((prev) =>
      prev.map((p) => (ids.includes(p.id) ? { ...p, is_active: true } : p))
    )
    try {
      await Promise.all(
        ids.map((id) => providersApi.updateProvider(id, { is_active: true }))
      )
    } catch {
      fetchData()
    }
  }

  // --- Derived data ---

  const providerTypes = useMemo(
    () => [...new Set(providers.map((p) => p.provider))].sort(),
    [providers]
  )

  const filteredProviders = useMemo(() => {
    let result = [...providers]

    // Filter by provider type
    if (providerFilter !== 'all') {
      result = result.filter((p) => p.provider === providerFilter)
    }

    // Filter by status
    if (statusFilter === 'active') {
      result = result.filter((p) => p.is_active)
    } else if (statusFilter === 'inactive') {
      result = result.filter((p) => !p.is_active)
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(
        (p) =>
          (p.name || '').toLowerCase().includes(q) ||
          p.provider.toLowerCase().includes(q)
      )
    }

    // Sort
    if (sortMode === 'remaining-asc') {
      result.sort((a, b) => {
        const aMin = Math.min(
          ...(a.quotas || []).map((q) => q.remaining_percentage ?? 100),
          100
        )
        const bMin = Math.min(
          ...(b.quotas || []).map((q) => q.remaining_percentage ?? 100),
          100
        )
        return aMin - bMin
      })
    } else if (sortMode === 'remaining-desc') {
      result.sort((a, b) => {
        const aMin = Math.min(
          ...(a.quotas || []).map((q) => q.remaining_percentage ?? 100),
          0
        )
        const bMin = Math.min(
          ...(b.quotas || []).map((q) => q.remaining_percentage ?? 100),
          0
        )
        return bMin - aMin
      })
    }

    // Expiring first
    if (expiringFirst) {
      const getEarliestReset = (p) => {
        const times = (p.quotas || [])
          .map((q) =>
            q.reset_at ? new Date(q.reset_at).getTime() : Infinity
          )
          .filter((t) => Number.isFinite(t))
        return times.length > 0 ? Math.min(...times) : Infinity
      }
      result.sort((a, b) => getEarliestReset(a) - getEarliestReset(b))
    }

    return result
  }, [
    providers,
    providerFilter,
    statusFilter,
    searchQuery,
    sortMode,
    expiringFirst,
  ])

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [providerFilter, statusFilter, searchQuery, sortMode, expiringFirst, pageSize])

  // --- Summary stats ---

  const totalProviders = providers.length
  const activeWithLimits = providers.filter(
    (p) => p.is_active && p.quotas?.length > 0
  ).length
  const lowQuotas = providers.reduce((acc, p) => {
    if (!p.quotas) return acc
    return (
      acc +
      p.quotas.filter((q) => (q.remaining_percentage ?? 100) <= 30).length
    )
  }, 0)

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filteredProviders.length / pageSize))
  const safePage = Math.min(currentPage, totalPages)
  const paginatedProviders = filteredProviders.slice(
    (safePage - 1) * pageSize,
    safePage * pageSize
  )
  const pageStart = filteredProviders.length === 0 ? 0 : (safePage - 1) * pageSize + 1
  const pageEnd = Math.min(safePage * pageSize, filteredProviders.length)

  // --- Loading / Error / Empty ---

  if (loading) return <LoadingSkeleton />
  if (error && providers.length === 0)
    return <ErrorState message={error} onRetry={fetchData} />
  if (providers.length === 0) return <EmptyConnectionsState />

  const hasActiveFilters =
    providerFilter !== 'all' ||
    statusFilter !== 'all' ||
    searchQuery.trim() !== '' ||
    sortMode !== 'default' ||
    expiringFirst

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">
            Quota Tracker
          </h1>
          <p className="text-[11px] text-zinc-500">
            Monitor provider API usage and limits
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-colors cursor-pointer ${
                autoRefresh
                  ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-600/30'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
              }`}
            >
              {autoRefresh ? (
                <>
                  <Pause size={11} /> Auto ({countdown}s)
                </>
              ) : (
                <>
                  <Play size={11} /> Paused
                </>
              )}
            </button>
            <div className="relative">
              <select
                value={refreshInterval}
                onChange={(e) => {
                  const val = Number(e.target.value)
                  setRefreshInterval(val)
                  setCountdown(val)
                }}
                className="appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-2 py-1.5 pr-6 text-[11px] text-zinc-400 focus:outline-none focus:border-zinc-600 cursor-pointer"
              >
                {REFRESH_INTERVALS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
            </div>
          </div>

          <button
            onClick={() => {
              fetchData()
              setCountdown(refreshInterval)
            }}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700 hover:bg-zinc-700 hover:text-zinc-200 transition-colors cursor-pointer"
          >
            <RefreshCw size={11} />
            Refresh
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SummaryStat
          icon={Server}
          label="Total Providers"
          value={totalProviders}
          bgClass="bg-blue-600/20"
          textClass="text-blue-400"
        />
        <SummaryStat
          icon={Settings}
          label="Active with Limits"
          value={activeWithLimits}
          bgClass="bg-emerald-600/20"
          textClass="text-emerald-400"
        />
        <SummaryStat
          icon={AlertTriangle}
          label="Low Quotas"
          value={lowQuotas}
          bgClass={lowQuotas > 0 ? 'bg-red-600/20' : 'bg-zinc-800'}
          textClass={lowQuotas > 0 ? 'text-red-400' : 'text-zinc-500'}
        />
      </div>

      {/* Filters bar */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[160px] max-w-[240px]">
          <Search
            size={12}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-500"
          />
          <input
            type="text"
            placeholder="Search connections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-zinc-800/80 border border-zinc-700/50 rounded-md pl-7 pr-7 py-1 text-[11px] text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 cursor-pointer"
            >
              <X size={12} />
            </button>
          )}
        </div>

        {/* Provider filter */}
        {providerTypes.length > 1 && (
          <FilterDropdown
            label="Provider"
            value={providerFilter}
            options={[
              { value: 'all', label: 'All providers' },
              ...providerTypes.map((t) => ({
                value: t,
                label: t.charAt(0).toUpperCase() + t.slice(1),
              })),
            ]}
            onChange={setProviderFilter}
          />
        )}

        {/* Status filter */}
        <FilterDropdown
          label="Status"
          value={statusFilter}
          options={STATUS_OPTIONS}
          onChange={setStatusFilter}
        />

        {/* Sort */}
        <FilterDropdown
          label="Sort"
          value={sortMode}
          options={SORT_OPTIONS}
          onChange={setSortMode}
        />

        {/* Expiring first toggle */}
        <button
          onClick={() => setExpiringFirst(!expiringFirst)}
          className={`flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-colors cursor-pointer ${
            expiringFirst
              ? 'bg-amber-600/20 text-amber-400 border border-amber-600/30'
              : 'bg-zinc-800/80 text-zinc-500 border border-zinc-700/50'
          }`}
          title="Sort by earliest reset time"
        >
          <Timer size={10} />
          Expiring first
        </button>

        {/* Clear filters */}
        {hasActiveFilters && (
          <button
            onClick={() => {
              setProviderFilter('all')
              setStatusFilter('all')
              setSearchQuery('')
              setSortMode('default')
              setExpiringFirst(false)
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-zinc-800/80 text-zinc-400 border border-zinc-700/50 hover:text-zinc-200 transition-colors cursor-pointer"
          >
            <X size={10} />
            Clear
          </button>
        )}

        <div className="flex-1" />

        {/* Bulk actions */}
        <button
          onClick={handleBulkDisableDepleted}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-zinc-800/80 text-amber-400 border border-amber-600/30 hover:bg-amber-600/10 transition-colors cursor-pointer"
          title="Disable connections with quota ≤ 5%"
        >
          <ZapOff size={10} />
          Disable Depleted
        </button>
        <button
          onClick={handleBulkEnableAll}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-zinc-800/80 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/10 transition-colors cursor-pointer"
          title="Re-enable all inactive connections"
        >
          <Zap size={10} />
          Enable All
        </button>
      </div>

      {/* Provider cards grid - 2 column */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {paginatedProviders.map((provider) => (
          <ProviderQuotaCard
            key={provider.id}
            provider={provider}
            onRefresh={handleRefreshProvider}
            isRefreshing={refreshingId === provider.id}
            isLoadingUsage={loadingUsage.has(provider.id)}
            onToggle={handleToggleActive}
            onEdit={setEditingProvider}
            onDelete={(p) => setConfirmAction({ type: 'delete', provider: p })}
          />
        ))}
      </div>

      {filteredProviders.length === 0 && (
        <div className="text-center py-8">
          <p className="text-xs text-zinc-500">
            No providers match the selected filters.
          </p>
          {hasActiveFilters && (
            <button
              onClick={() => {
                setProviderFilter('all')
                setStatusFilter('all')
                setSearchQuery('')
                setSortMode('default')
                setExpiringFirst(false)
              }}
              className="mt-2 text-[11px] text-blue-400 hover:text-blue-300 cursor-pointer"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Pagination */}
      {filteredProviders.length > 0 && (
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600">
              {pageStart}-{pageEnd} of {filteredProviders.length}
            </span>
            <div className="relative">
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="appearance-none bg-zinc-800/80 border border-zinc-700/50 rounded-md px-2 py-1 pr-6 text-[10px] text-zinc-400 focus:outline-none focus:border-zinc-600 cursor-pointer"
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    {size} / page
                  </option>
                ))}
              </select>
              <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none" />
            </div>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => setCurrentPage(Math.max(1, safePage - 1))}
                disabled={safePage === 1}
                className="flex h-7 items-center rounded-md border border-zinc-700 px-2.5 text-[10px] text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                Prev
              </button>
              <span className="text-[10px] text-zinc-500 px-2">
                Page {safePage} / {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage(Math.min(totalPages, safePage + 1))}
                disabled={safePage === totalPages}
                className="flex h-7 items-center rounded-md border border-zinc-700 px-2.5 text-[10px] text-zinc-300 transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {editingProvider && (
        <EditNameModal
          currentName={editingProvider.name}
          onSave={handleEditName}
          onCancel={() => setEditingProvider(null)}
        />
      )}

      {confirmAction?.type === 'delete' && (
        <ConfirmModal
          title="Delete Connection"
          message={`Are you sure you want to delete "${confirmAction.provider.name || confirmAction.provider.provider}"? This action cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}

      {confirmAction?.type === 'bulk-disable' && (
        <ConfirmModal
          title="Disable Depleted Connections"
          message={`This will disable ${confirmAction.count} connection(s) with quota ≤ 5%. They can be re-enabled later.`}
          confirmLabel={`Disable ${confirmAction.count}`}
          confirmClass="bg-amber-600 text-white hover:bg-amber-700"
          onConfirm={handleBulkDisableConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
