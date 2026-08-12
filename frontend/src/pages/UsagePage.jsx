import { useState, useEffect, useCallback, Fragment } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import {
  Activity,
  ChevronDown,
  ChevronRight,
  BarChart3,
  X,
  ChevronLeft,
  ChevronsLeft,
  ChevronsRight,
  Loader2,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import { usageApi } from '../api/usage'
import ProviderTopology from '../components/ProviderTopology'
import useCatalogStore from '../stores/catalogStore'
import { subscribeUsageStream } from '../api/usageStream'

const RECENT_REQUESTS_LIMIT = 20

function recentRequestKey(req) {
  return [
    req?.timestamp,
    req?.provider,
    req?.model,
    req?.promptTokens,
    req?.completionTokens,
    req?.status,
  ].join('|')
}

/** Merge WS ring-buffer rows into REST recent list (newest first). */
function mergeRecentRequests(prev, incoming) {
  const map = new Map()
  for (const req of prev || []) {
    if (!req) continue
    map.set(recentRequestKey(req), req)
  }
  for (const req of incoming || []) {
    if (!req) continue
    map.set(recentRequestKey(req), req)
  }
  return Array.from(map.values())
    .sort((a, b) =>
      String(b.timestamp || '').localeCompare(String(a.timestamp || '')),
    )
    .slice(0, RECENT_REQUESTS_LIMIT)
}

// --- Number formatting helpers ---

const nf = new Intl.NumberFormat('en-US')

function formatTokens(n) {
  if (n == null) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K'
  return nf.format(n)
}

function formatCost(n) {
  if (n == null || n === 0) return '$0.00'
  if (n < 0.01) return '$' + n.toFixed(4)
  return '$' + n.toFixed(2)
}

function formatNumber(n) {
  return nf.format(n ?? 0)
}

// --- Period tabs ---

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: '24h', label: '24h' },
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
  { value: '60d', label: '60D' },
]

// --- Chart view modes ---

const CHART_MODES = [
  { key: 'tokens', label: 'Tokens', color: 'indigo' },
  { key: 'cost', label: 'Cost', color: 'amber' },
]

// --- Custom tooltip ---

function ChartTooltip({ active, payload, label, chartMode }) {
  if (!active || !payload?.length) return null
  const val = payload[0]?.value ?? 0
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 shadow-xl">
      <p className="text-xs text-zinc-400 mb-1">{label}</p>
      <p className="text-sm font-semibold text-zinc-100">
        {chartMode === 'tokens' ? formatTokens(val) + ' tokens' : formatCost(val)}
      </p>
    </div>
  )
}

// --- Loading skeleton ---

function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse rounded-lg bg-zinc-800/60 ${className}`} />
  )
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="px-4 py-3 space-y-2">
              <Skeleton className="w-16 h-3" />
              <Skeleton className="w-20 h-7" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <Skeleton className="h-[400px] lg:col-span-3" />
        <Skeleton className="h-[400px] lg:col-span-2" />
      </div>
      <Skeleton className="h-[300px]" />
      <Skeleton className="h-[300px]" />
    </div>
  )
}

// --- Empty state ---

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
      <div className="w-16 h-16 rounded-2xl bg-zinc-800 flex items-center justify-center mb-6">
        <Activity size={28} className="text-zinc-500" />
      </div>
      <h2 className="text-xl font-bold text-zinc-300 mb-2">No usage data yet</h2>
      <p className="text-sm text-zinc-500 max-w-md">
        Usage analytics will appear here once API requests are routed through 9Router.
      </p>
    </div>
  )
}

// --- Time ago formatter ---

function formatTimeAgo(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const diffSec = Math.floor((now - d) / 1000)
  if (diffSec < 5) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay}d ago`
}

// --- Segmented control (tabs) ---

function SegmentedControl({ options, value, onChange, size = 'md' }) {
  const sizeClasses = size === 'sm' ? 'text-xs px-3 py-1' : 'text-sm px-4 py-1.5'
  return (
    <div className="inline-flex rounded-lg border border-zinc-700 bg-zinc-800/50 p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`${sizeClasses} rounded-md font-medium transition-colors cursor-pointer ${
            value === opt.value
              ? 'bg-zinc-700 text-zinc-100 shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// --- Stat card (minimal, no icon) ---

function StatCard({ label, value, valueClass = 'text-zinc-100', subtext, className = '' }) {
  return (
    <Card className={className}>
      <CardContent className="px-4 py-3">
        <p className="text-xs text-zinc-400 uppercase tracking-wider mb-1">{label}</p>
        <p className={`text-2xl font-bold ${valueClass}`}>{value}</p>
        {subtext && (
          <p className="text-xs text-zinc-500 mt-1">{subtext}</p>
        )}
      </CardContent>
    </Card>
  )
}

// --- Usage chart ---

function UsageChart({ data, chartMode, onToggleMode }) {
  const isTokens = chartMode === 'tokens'
  const dataKey = isTokens ? 'tokens' : 'cost'

  // Suppress Recharts ResponsiveContainer warning on first render
  useEffect(() => {
    const origWarn = console.warn
    console.warn = (...args) => {
      if (args[0]?.includes?.('width') && args[0]?.includes?.('height')) return
      origWarn(...args)
    }
    return () => { console.warn = origWarn }
  }, [])

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center justify-between mb-4">
            <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
              {CHART_MODES.map((mode) => (
                <button
                  key={mode.key}
                  onClick={() => onToggleMode(mode.key)}
                  className={`px-4 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                    chartMode === mode.key
                      ? 'bg-orange-500 text-white'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                  }`}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">
            No chart data for this period
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent>
        <div className="flex items-center justify-between mb-4">
          <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
            {CHART_MODES.map((mode) => (
              <button
                key={mode.key}
                onClick={() => onToggleMode(mode.key)}
                className={`px-4 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                  chartMode === mode.key
                    ? 'bg-orange-500 text-white'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                }`}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>
        <div style={{ width: '100%', height: 256 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradTokens" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradCost" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: '#71717a', fontSize: 12 }}
                axisLine={{ stroke: '#3f3f46' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#71717a', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => (isTokens ? formatTokens(v) : formatCost(v))}
                width={60}
              />
              <Tooltip content={<ChartTooltip chartMode={chartMode} />} />
              <Area
                type="monotone"
                dataKey={dataKey}
                stroke={isTokens ? '#6366f1' : '#f59e0b'}
                strokeWidth={2}
                fill={isTokens ? 'url(#gradTokens)' : 'url(#gradCost)'}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

// --- Recent Requests panel ---

function RecentRequests({ requests }) {
  const [, setTick] = useState(0)

  // Auto-update time-ago every second
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(interval)
  }, [])

  if (!requests || requests.length === 0) return null

  return (
    <Card className="flex flex-col">
      <CardHeader className="shrink-0">
        <h3 className="text-sm font-semibold text-zinc-100 uppercase tracking-wider">Recent Requests</h3>
      </CardHeader>
      <CardContent className="p-0 flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="px-4 py-2.5 text-left text-xs font-medium text-zinc-400">Model</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-zinc-400">In / Out</th>
              <th className="px-4 py-2.5 text-right text-xs font-medium text-zinc-400">When</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((req, idx) => (
              <tr key={idx} className="border-b border-zinc-800/50 last:border-b-0">
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                    <span className="font-mono text-xs text-zinc-200 truncate max-w-[180px]">{req.model}</span>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-xs whitespace-nowrap">
                  <span className="text-orange-400">{formatTokens(req.promptTokens)}</span>
                  <span className="text-zinc-500 mx-0.5">↑</span>
                  <span className="text-zinc-400 mx-1">/</span>
                  <span className="text-emerald-400">{formatTokens(req.completionTokens)}</span>
                  <span className="text-zinc-500 mx-0.5">↓</span>
                </td>
                <td className="px-4 py-2.5 text-right text-zinc-500 text-xs whitespace-nowrap">
                  {formatTimeAgo(req.timestamp)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

// --- Usage Breakdown table (Model / Provider / Account / Endpoint) ---

const BREAKDOWN_OPTIONS = [
  { key: 'byModel', label: 'Usage by Model' },
  { key: 'byProvider', label: 'Usage by Provider' },
  { key: 'byAccount', label: 'Usage by Account' },
  { key: 'byEndpoint', label: 'Usage by Endpoint' },
]

function getRowName(row, groupKey) {
  switch (groupKey) {
    case 'byProvider': return row.name
    case 'byAccount': return row.accountName || row.name
    case 'byEndpoint': return row.endpoint || row.name
    default: return row.name // byModel
  }
}

function getRowSecondary(row, groupKey) {
  switch (groupKey) {
    case 'byModel': return row.provider || '—'
    case 'byAccount': return row.provider || '—'
    case 'byEndpoint': return row.provider || '—'
    default: return null
  }
}

function UsageBreakdownTable({ stats, viewMode, onToggleViewMode }) {
  const [groupKey, setGroupKey] = useState('byModel')
  const [expandedRows, setExpandedRows] = useState({})

  const toggleRow = (key) => {
    setExpandedRows((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const data = stats?.[groupKey] || []
  const sorted = [...data].sort((a, b) => (b.requests || 0) - (a.requests || 0))
  const hasSecondary = groupKey === 'byModel' || groupKey === 'byAccount' || groupKey === 'byEndpoint'

  // Column count for colSpan in expanded row
  // expand icon + name + [provider?] + requests + lastUsed + cost cols + token cols
  const colCount = 1 + 1 + (hasSecondary ? 1 : 0) + 1 + 1 + (viewMode === 'cost' ? 3 : 2)

  return (
    <Card>
      <CardContent className="p-0">
        {/* Header row with dropdown and toggle */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700/50">
          <div className="relative">
            <select
              value={groupKey}
              onChange={(e) => { setGroupKey(e.target.value); setExpandedRows({}) }}
              className="appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 cursor-pointer pr-8 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
              style={{ colorScheme: 'dark' }}
            >
              {BREAKDOWN_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
            <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 pointer-events-none" />
          </div>
          <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
            <button
              onClick={() => onToggleViewMode('cost')}
              className={`px-4 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                viewMode === 'cost'
                  ? 'bg-orange-500 text-white'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
              }`}
            >
              Costs
            </button>
            <button
              onClick={() => onToggleViewMode('tokens')}
              className={`px-4 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                viewMode === 'tokens'
                  ? 'bg-orange-500 text-white'
                  : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
              }`}
            >
              Tokens
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="w-8 px-4 py-3" />
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                  {groupKey === 'byEndpoint' ? 'Endpoint' : groupKey === 'byAccount' ? 'Account' : groupKey === 'byProvider' ? 'Provider' : 'Model'}
                </th>
                {hasSecondary && (
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Provider</th>
                )}
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Requests</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Last Used</th>
                {viewMode === 'cost' && (
                  <>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Input Cost</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Output Cost</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Total Cost</th>
                  </>
                )}
                {viewMode === 'tokens' && (
                  <>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Input</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Output</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row, idx) => {
                const rowKey = `${groupKey}-${getRowName(row, groupKey)}-${idx}`
                const isExpanded = !!expandedRows[rowKey]
                const secondary = getRowSecondary(row, groupKey)
                return (
                  <Fragment key={rowKey}>
                    <tr
                      onClick={() => toggleRow(rowKey)}
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        {isExpanded ? (
                          <ChevronDown size={14} className="text-zinc-400" />
                        ) : (
                          <ChevronRight size={14} className="text-zinc-500" />
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-zinc-100">{getRowName(row, groupKey)}</td>
                      {hasSecondary && (
                        <td className="px-4 py-3 text-zinc-400">{secondary}</td>
                      )}
                      <td className="px-4 py-3 text-right text-zinc-200 font-mono">{formatNumber(row.requests)}</td>
                      <td className="px-4 py-3 text-right text-zinc-500 text-xs">{formatTimeAgo(row.lastUsed)}</td>
                      {viewMode === 'cost' && (
                        <>
                          <td className="px-4 py-3 text-right text-zinc-500 font-mono text-xs">{formatCost(row.cost * 0.6)}</td>
                          <td className="px-4 py-3 text-right text-zinc-500 font-mono text-xs">{formatCost(row.cost * 0.4)}</td>
                          <td className="px-4 py-3 text-right text-amber-400/80 font-mono text-xs">{formatCost(row.cost)}</td>
                        </>
                      )}
                      {viewMode === 'tokens' && (
                        <>
                          <td className="px-4 py-3 text-right text-blue-400 font-mono text-xs">{formatTokens(row.promptTokens)}</td>
                          <td className="px-4 py-3 text-right text-emerald-400 font-mono text-xs">{formatTokens(row.completionTokens)}</td>
                        </>
                      )}
                    </tr>
                    {isExpanded && (
                      <tr className="bg-zinc-900/50">
                        <td colSpan={colCount} className="px-8 py-4">
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                            <div>
                              <span className="text-zinc-500 block mb-1">Total Requests</span>
                              <span className="text-zinc-200 text-sm font-medium">{formatNumber(row.requests)}</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block mb-1">Input Tokens</span>
                              <span className="text-blue-400 text-sm font-medium">{formatNumber(row.promptTokens)}</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block mb-1">Output Tokens</span>
                              <span className="text-emerald-400 text-sm font-medium">{formatNumber(row.completionTokens)}</span>
                            </div>
                            <div>
                              <span className="text-zinc-500 block mb-1">Estimated Cost</span>
                              <span className="text-amber-400 text-sm font-medium">{formatCost(row.cost)}</span>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
        {sorted.length === 0 && (
          <div className="text-center py-12">
            <BarChart3 size={24} className="mx-auto text-zinc-600 mb-2" />
            <p className="text-sm text-zinc-500">No data for this period</p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// --- Detail drawer (slide-over from right) ---

function DetailDrawer({ isOpen, onClose, detail, loading }) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [isOpen])

  if (!isOpen) return null

  const resp = detail?.response
  const respThinking = resp?.thinking || null
  const respContent = resp?.content || null

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-2xl bg-zinc-900 border-l border-zinc-700 overflow-y-auto shadow-2xl animate-[slideInRight_0.2s_ease-out]">
        <style>{`
          @keyframes slideInRight {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
        `}</style>

        <div className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 bg-zinc-900 border-b border-zinc-800">
          <h2 className="text-lg font-bold text-zinc-100">Request Details</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
          >
            <X size={18} className="text-zinc-400" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={20} className="animate-spin text-zinc-400" />
            </div>
          ) : !detail ? (
            <div className="text-center py-12 text-zinc-500 text-sm">
              No detail data available
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-zinc-500">ID:</span>{' '}
                  <span className="break-all font-mono text-zinc-200">{detail.id}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Timestamp:</span>{' '}
                  <span className="text-zinc-200">{new Date(detail.timestamp).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Provider:</span>{' '}
                  <span className="text-indigo-400 font-medium">{detail.provider || '—'}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Model:</span>{' '}
                  <span className="text-zinc-200 font-mono text-xs">{detail.model || '—'}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Status:</span>{' '}
                  <span className={`font-medium ${
                    detail.status === 'ok' || detail.status === 'success'
                      ? 'text-emerald-400'
                      : 'text-red-400'
                  }`}>
                    {detail.status}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500">Cost:</span>{' '}
                  <span className="text-amber-400 font-mono">{formatCost(detail.cost)}</span>
                </div>
                <div>
                  <span className="text-zinc-500">Input Tokens:</span>{' '}
                  <span className="text-blue-400 font-mono">
                    {formatNumber(detail.prompt_tokens)}
                  </span>
                </div>
                <div>
                  <span className="text-zinc-500">Output Tokens:</span>{' '}
                  <span className="text-emerald-400 font-mono">
                    {formatNumber(detail.completion_tokens)}
                  </span>
                </div>
                {(detail.latency_ttft != null || detail.latency_total != null) && (
                  <>
                    <div>
                      <span className="text-zinc-500">Latency TTFT:</span>{' '}
                      <span className="text-violet-400 font-mono">
                        {detail.latency_ttft != null ? `${detail.latency_ttft}ms` : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Latency Total:</span>{' '}
                      <span className="text-violet-400 font-mono">
                        {detail.latency_total != null ? `${detail.latency_total}ms` : '—'}
                      </span>
                    </div>
                  </>
                )}
              </div>

              <div className="space-y-4">
                {detail.request != null && (
                  <CollapsibleSection title="1. Client Request (Input)" defaultOpen={true}>
                    <pre className="max-h-[400px] overflow-auto rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap break-all">
                      {JSON.stringify(detail.request, null, 2)}
                    </pre>
                  </CollapsibleSection>
                )}

                {detail.provider_request != null && (
                  <CollapsibleSection title="2. Provider Request (Translated)">
                    <pre className="max-h-[400px] overflow-auto rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap break-all">
                      {JSON.stringify(detail.provider_request, null, 2)}
                    </pre>
                  </CollapsibleSection>
                )}

                {detail.provider_response != null && (
                  <CollapsibleSection title="3. Provider Response (Raw)">
                    <pre className="max-h-[400px] overflow-auto rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap break-all">
                      {JSON.stringify(detail.provider_response, null, 2)}
                    </pre>
                  </CollapsibleSection>
                )}

                {detail.response != null && (
                  <CollapsibleSection title="4. Client Response (Final)" defaultOpen={true}>
                    {respThinking && (
                      <div className="mb-4">
                        <p className="text-xs font-semibold text-amber-400/80 uppercase tracking-wider mb-2">Thinking</p>
                        <pre className="max-h-[300px] overflow-auto rounded-lg border border-amber-700/30 bg-amber-950/20 p-4 font-mono text-xs text-amber-200/80 whitespace-pre-wrap break-all">
                          {respThinking}
                        </pre>
                      </div>
                    )}
                    {respContent && (
                      <div>
                        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Content</p>
                        <pre className="max-h-[400px] overflow-auto rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap break-all">
                          {respContent}
                        </pre>
                      </div>
                    )}
                    {!respThinking && !respContent && (
                      <pre className="max-h-[400px] overflow-auto rounded-lg border border-zinc-700/50 bg-zinc-800/50 p-4 font-mono text-xs text-zinc-300 whitespace-pre-wrap break-all">
                        {JSON.stringify(detail.response, null, 2)}
                      </pre>
                    )}
                  </CollapsibleSection>
                )}

                {!detail.request && !detail.provider_request && !detail.provider_response && !detail.response && (
                  <div className="text-center py-8 text-zinc-500 text-sm">
                    No request/response payloads available for this entry
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Collapsible section ---

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [isOpen, setIsOpen] = useState(defaultOpen)

  return (
    <div className="border border-zinc-700/50 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-3 bg-zinc-800/30 hover:bg-zinc-800/50 transition-colors cursor-pointer"
      >
        <span className="font-semibold text-sm text-zinc-200">{title}</span>
        <ChevronRight
          size={16}
          className={`text-zinc-400 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`}
        />
      </button>
      {isOpen && (
        <div className="p-4 border-t border-zinc-700/50">
          {children}
        </div>
      )}
    </div>
  )
}

// --- Pagination ---

function Pagination({ currentPage, pageSize, totalItems, totalPages, onPageChange, onPageSizeChange }) {
  const startItem = (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, totalItems)

  const getPageNumbers = () => {
    const pages = []
    const maxVisible = 5
    let start = Math.max(1, currentPage - Math.floor(maxVisible / 2))
    let end = Math.min(totalPages, start + maxVisible - 1)

    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1)
    }

    for (let i = start; i <= end; i++) {
      pages.push(i)
    }
    return pages
  }

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3">
      <div className="flex items-center gap-4 text-sm text-zinc-400">
        <span>
          Showing {formatNumber(startItem)}-{formatNumber(endItem)} of {formatNumber(totalItems)}
        </span>
        <select
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300 cursor-pointer"
        >
          {[10, 20, 50].map((size) => (
            <option key={size} value={size}>{size} / page</option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="p-1.5 rounded hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          <ChevronsLeft size={16} className="text-zinc-400" />
        </button>
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-1.5 rounded hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          <ChevronLeft size={16} className="text-zinc-400" />
        </button>

        {getPageNumbers().map((page) => (
          <button
            key={page}
            onClick={() => onPageChange(page)}
            className={`min-w-[32px] h-8 rounded text-xs font-medium transition-colors cursor-pointer ${
              page === currentPage
                ? 'bg-blue-600 text-white'
                : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
            }`}
          >
            {page}
          </button>
        ))}

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-1.5 rounded hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          <ChevronRight size={16} className="text-zinc-400" />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="p-1.5 rounded hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
        >
          <ChevronsRight size={16} className="text-zinc-400" />
        </button>
      </div>
    </div>
  )
}

// --- CSV Export ---

function exportToCSV(details) {
  const headers = ['Timestamp', 'Model', 'Provider', 'Input Tokens', 'Output Tokens', 'Cost', 'Latency TTFT', 'Latency Total', 'Status']
  const rows = details.map((d) => [
    new Date(d.timestamp).toISOString(),
    d.model,
    d.provider,
    d.prompt_tokens || 0,
    d.completion_tokens || 0,
    d.cost || 0,
    d.latency_ttft || 0,
    d.latency_total || 0,
    d.status,
  ])

  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `usage-details-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// --- Details Tab ---

function RequestDetailsTab() {
  const [details, setDetails] = useState([])
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 20,
    totalItems: 0,
    totalPages: 0,
  })
  const [loading, setLoading] = useState(false)
  const [selectedDetail, setSelectedDetail] = useState(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [providers, setProviders] = useState([])
  const [filters, setFilters] = useState({
    provider: '',
    model: '',
    startDate: '',
    endDate: '',
  })

  const fetchProviders = useCallback(async () => {
    try {
      const res = await usageApi.getUsageProviders()
      setProviders(res.data?.providers || [])
    } catch (err) {
      console.error('Failed to fetch providers:', err)
    }
  }, [])

  const fetchDetails = useCallback(async () => {
    setLoading(true)
    try {
      const filterParams = {}
      if (filters.provider) filterParams.provider = filters.provider
      if (filters.model) filterParams.model = filters.model
      if (filters.startDate) filterParams.startDate = filters.startDate
      if (filters.endDate) filterParams.endDate = filters.endDate

      const res = await usageApi.getRequestDetails(
        pagination.page,
        pagination.pageSize,
        filterParams,
      )
      const data = res.data
      setDetails(data.details || [])
      setPagination((prev) => ({ ...prev, ...(data.pagination || {}) }))
    } catch (err) {
      console.error('Failed to fetch request details:', err)
    } finally {
      setLoading(false)
    }
  }, [pagination.page, pagination.pageSize, filters])

  useEffect(() => {
    useCatalogStore.getState().fetchCatalog()
    fetchProviders() // eslint-disable-line react-hooks/set-state-in-effect
  }, [fetchProviders])

  useEffect(() => {
    fetchDetails() // eslint-disable-line react-hooks/set-state-in-effect

    // Polling fallback: refresh details every 30s
    const pollTimer = setInterval(fetchDetails, 30000)
    return () => clearInterval(pollTimer)
  }, [fetchDetails])

  const [detailLoading, setDetailLoading] = useState(false)

  const handleViewDetail = async (detail) => {
    setSelectedDetail(null)
    setIsDrawerOpen(true)
    setDetailLoading(true)
    try {
      const res = await usageApi.getRequestDetail(detail.id)
      setSelectedDetail(res.data)
    } catch (err) {
      console.error('Failed to fetch request detail:', err)
      setSelectedDetail(detail)
    } finally {
      setDetailLoading(false)
    }
  }

  const handlePageChange = (newPage) => {
    setPagination((prev) => ({ ...prev, page: newPage }))
  }

  const handlePageSizeChange = (newPageSize) => {
    setPagination((prev) => ({ ...prev, pageSize: newPageSize, page: 1 }))
  }

  const handleClearFilters = () => {
    setFilters({ provider: '', model: '', startDate: '', endDate: '' })
  }

  const hasActiveFilters = filters.provider || filters.model || filters.startDate || filters.endDate

  return (
    <div className="flex min-w-0 flex-col gap-6">
      {/* Filter card */}
      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">Provider</label>
              <select
                value={filters.provider}
                onChange={(e) => setFilters({ ...filters, provider: e.target.value })}
                className="h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 w-full cursor-pointer"
              >
                <option value="">All Providers</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">Model</label>
              <input
                type="text"
                placeholder="e.g. gpt-4o"
                value={filters.model}
                onChange={(e) => setFilters({ ...filters, model: e.target.value })}
                className="h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 w-full"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">Start Date</label>
              <input
                type="datetime-local"
                value={filters.startDate}
                onChange={(e) => setFilters({ ...filters, startDate: e.target.value })}
                className="h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 w-full [color-scheme:dark]"
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">End Date</label>
              <input
                type="datetime-local"
                value={filters.endDate}
                onChange={(e) => setFilters({ ...filters, endDate: e.target.value })}
                className="h-9 px-3 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500/40 w-full [color-scheme:dark]"
              />
            </div>

            <div className="flex flex-col gap-2">
              <span className="hidden text-sm font-medium text-transparent lg:block" aria-hidden="true">Clear</span>
              <button
                onClick={handleClearFilters}
                disabled={!hasActiveFilters}
                className="h-9 px-4 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer w-full"
              >
                Clear Filters
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <span className="hidden text-sm font-medium text-transparent lg:block" aria-hidden="true">Export</span>
              <button
                onClick={() => exportToCSV(details)}
                disabled={details.length === 0}
                className="h-9 px-4 rounded-lg border border-zinc-700 bg-zinc-800 text-sm text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer w-full"
              >
                Export CSV
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Request details table */}
      <Card className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px]">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Model</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Provider</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Input Tokens</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Output Tokens</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Latency</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Cost</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Status</th>
                <th className="text-center px-4 py-3 text-xs font-medium text-zinc-400 uppercase tracking-wider">Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="px-4 py-12 text-center text-zinc-500">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 size={18} className="animate-spin" />
                      Loading...
                    </div>
                  </td>
                </tr>
              ) : details.length === 0 ? (
                <tr>
                  <td colSpan="9" className="px-4 py-12 text-center text-zinc-500">
                    No request details found
                  </td>
                </tr>
              ) : (
                details.map((detail, index) => {
                  const isSuccess = detail.status === 'ok' || detail.status === 'success'
                  return (
                    <tr
                      key={`${detail.id}-${index}`}
                      className="border-b border-zinc-800/50 last:border-b-0 hover:bg-zinc-800/20 transition-colors"
                    >
                      <td className="whitespace-nowrap px-4 py-3 text-sm text-zinc-300">
                        {new Date(detail.timestamp).toLocaleString()}
                      </td>
                      <td className="max-w-[260px] truncate px-4 py-3 font-mono text-sm text-zinc-200">
                        {detail.model}
                      </td>
                      <td className="max-w-[180px] truncate px-4 py-3 text-sm text-zinc-200 font-medium">
                        {detail.provider || '—'}
                      </td>
                      <td className="px-4 py-3 text-sm text-blue-400 text-right font-mono">
                        {formatNumber(detail.prompt_tokens)}
                      </td>
                      <td className="px-4 py-3 text-sm text-emerald-400 text-right font-mono">
                        {formatNumber(detail.completion_tokens)}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-zinc-400">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-mono">{detail.latency_ttft ? `${detail.latency_ttft}ms` : '—'}</span>
                          <span className="font-mono text-zinc-500">{detail.latency_total ? `${detail.latency_total}ms` : '—'}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-amber-400 text-right font-mono">
                        {formatCost(detail.cost)}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          isSuccess
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}>
                          {detail.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => handleViewDetail(detail)}
                          className="px-3 py-1 rounded border border-zinc-700 text-xs font-medium text-zinc-300 hover:bg-zinc-700 hover:text-zinc-100 transition-colors cursor-pointer"
                        >
                          Detail
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {!loading && details.length > 0 && (
          <div className="border-t border-zinc-800">
            <Pagination
              currentPage={pagination.page}
              pageSize={pagination.pageSize}
              totalItems={pagination.totalItems}
              totalPages={pagination.totalPages}
              onPageChange={handlePageChange}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        )}
      </Card>

      {/* Detail drawer */}
      <DetailDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        detail={selectedDetail}
        loading={detailLoading}
      />
    </div>
  )
}

// --- Main Usage Page ---

const TAB_OPTIONS = [
  { value: 'overview', label: 'Overview' },
  { value: 'details', label: 'Details' },
]

export default function UsagePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [period, setPeriod] = useState('today')
  const [chartMode, setChartMode] = useState('tokens')
  const [viewModelMode, setViewModelMode] = useState('cost')
  const [stats, setStats] = useState(null)
  const [chartData, setChartData] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasData, setHasData] = useState(false)
  const [activeRequests, setActiveRequests] = useState([])
  const [recentRequests, setRecentRequests] = useState([])
  const [errorProvider, setErrorProvider] = useState('')

  // Table view & sort from URL
  const tabParam = searchParams.get('tab')
  const activeTab = tabParam === 'details' ? 'details' : 'overview'

  const setUrlParam = (key, value) => {
    const params = new URLSearchParams(searchParams)
    params.set(key, value)
    setSearchParams(params, { replace: true })
  }

  const handleTabChange = (tab) => {
    if (tab === activeTab) return
    setUrlParam('tab', tab)
  }

  const fetchData = useCallback(async (p) => {
    setLoading(true)
    try {
      const [statsRes, chartRes] = await Promise.all([
        usageApi.getUsageStats(p),
        usageApi.getUsageChart(p),
      ])
      const statsData = statsRes.data
      setStats(statsData)
      setRecentRequests(statsData?.recentRequests || [])
      setChartData(chartRes.data || [])

      const totalReqs = statsData.totalRequests || 0
      setHasData(totalReqs > 0 || (chartRes.data && chartRes.data.length > 0))
    } catch (err) {
      console.error('Failed to fetch usage data:', err)
      setStats(null)
      setRecentRequests([])
      setChartData([])
      setHasData(false)
    } finally {
      setLoading(false)
    }
  }, [])

  // Topology providers come from stats.byProvider (grouped by provider name)

  useEffect(() => {
    if (activeTab === 'overview') {
      fetchData(period) // eslint-disable-line react-hooks/set-state-in-effect
    }
  }, [period, fetchData, activeTab])

  // WebSocket for real-time updates — shared socket (StrictMode-safe)
  useEffect(() => {
    if (activeTab !== 'overview') return
    const token = localStorage.getItem('token')
    if (!token) return

    return subscribeUsageStream(token, (data) => {
      if (Array.isArray(data.activeRequests)) {
        setActiveRequests(data.activeRequests)
      }
      // Merge WS ring into REST-loaded recent — never replace wholesale
      // (ring is empty after restart / incomplete during early notifies).
      if (
        Array.isArray(data.recentRequests)
        && data.recentRequests.length > 0
      ) {
        setRecentRequests((prev) =>
          mergeRecentRequests(prev, data.recentRequests),
        )
      }
      if (data.errorProvider !== undefined) {
        setErrorProvider(data.errorProvider)
      }
    })
  }, [activeTab])

  return (
    <div className="space-y-6">
      {/* Tabs + period selector row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <SegmentedControl
          options={TAB_OPTIONS}
          value={activeTab}
          onChange={handleTabChange}
        />
        {activeTab === 'overview' && (
          <SegmentedControl
            options={PERIODS}
            value={period}
            onChange={setPeriod}
            size="sm"
          />
        )}
      </div>

      {/* Overview tab */}
      {activeTab === 'overview' && (
        <>
          {loading ? (
            <LoadingSkeleton />
          ) : !hasData ? (
            <EmptyState />
          ) : (
            <>
              {/* Stat cards — 4 columns */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard
                  label="Total Requests"
                  value={nf.format(stats?.totalRequests ?? 0)}
                  valueClass="text-zinc-100"
                />
                <StatCard
                  label="Total Input Tokens"
                  value={nf.format(stats?.totalPromptTokens ?? 0)}
                  valueClass="text-orange-400"
                />
                <StatCard
                  label="Output Tokens"
                  value={nf.format(stats?.totalCompletionTokens ?? 0)}
                  valueClass="text-emerald-400"
                />
                <StatCard
                  label="Est. Cost"
                  value={`~${formatCost(stats?.totalCost)}`}
                  valueClass="text-amber-400"
                  subtext="Estimated, not actual billing"
                />
              </div>

              {/* Split layout: Topology + Recent Requests */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
                <div className="lg:col-span-3">
                  <ProviderTopology
                    providers={stats?.byProvider || []}
                    activeRequests={activeRequests}
                    lastProvider={recentRequests[0]?.provider || ''}
                    errorProvider={errorProvider}
                  />
                </div>
                <div className="lg:col-span-2 min-h-[400px]">
                  <RecentRequests requests={recentRequests} />
                </div>
              </div>

              {/* Token/Cost line chart */}
              <UsageChart
                data={chartData}
                chartMode={chartMode}
                onToggleMode={setChartMode}
              />

              {/* Usage breakdown table */}
              <UsageBreakdownTable
                stats={stats}
                viewMode={viewModelMode}
                onToggleViewMode={setViewModelMode}
              />
            </>
          )}
        </>
      )}

      {/* Details tab */}
      {activeTab === 'details' && <RequestDetailsTab />}
    </div>
  )
}
