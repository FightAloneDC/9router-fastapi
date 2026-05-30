/**
 * ModelAvailabilityBadge — compact inline status indicator
 *
 * Shows green when all models are operational, or amber/red when there are
 * issues, with a hover popover for details and cooldown clearing.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { CheckCircle, AlertTriangle, AlertCircle, HelpCircle, RefreshCw, XCircle } from 'lucide-react'
import { modelsApi } from '../api/models'

const STATUS_CONFIG = {
  available: { icon: CheckCircle, color: '#22c55e', label: 'Available' },
  cooldown: { icon: AlertTriangle, color: '#f59e0b', label: 'Cooldown' },
  unavailable: { icon: AlertCircle, color: '#ef4444', label: 'Unavailable' },
  unknown: { icon: HelpCircle, color: '#6b7280', label: 'Unknown' },
}

export default function ModelAvailabilityBadge() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(false)
  const [clearing, setClearing] = useState(null)
  const ref = useRef(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await modelsApi.getAvailability()
      setData(res.data)
    } catch {
      // silent fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Close popover on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setExpanded(false)
    }
    if (expanded) document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [expanded])

  const handleClearCooldown = async (provider, model) => {
    setClearing(`${provider}:${model}`)
    try {
      await modelsApi.clearCooldown(provider, model)
      await fetchStatus()
    } catch {
      // silent fail
    } finally {
      setClearing(null)
    }
  }

  if (loading) return null

  const models = data?.models || []
  const unavailableCount = data?.unavailableCount || models.filter((m) => m.status !== 'available').length
  const isHealthy = unavailableCount === 0

  // Group unhealthy models by provider
  const byProvider = {}
  models.forEach((m) => {
    if (m.status === 'available') return
    const key = m.provider || 'unknown'
    if (!byProvider[key]) byProvider[key] = []
    byProvider[key].push(m)
  })

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
          isHealthy
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500 hover:bg-emerald-500/15'
            : 'bg-amber-500/10 border-amber-500/20 text-amber-500 hover:bg-amber-500/15'
        }`}
      >
        {isHealthy ? (
          <CheckCircle size={14} />
        ) : (
          <AlertTriangle size={14} />
        )}
        {isHealthy
          ? 'All models operational'
          : `${unavailableCount} model${unavailableCount !== 1 ? 's' : ''} with issues`}
      </button>

      {expanded && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              {isHealthy ? (
                <CheckCircle size={16} className="text-emerald-500" />
              ) : (
                <AlertTriangle size={16} className="text-amber-500" />
              )}
              <span className="text-sm font-semibold text-zinc-100">Model Status</span>
            </div>
            <button
              onClick={fetchStatus}
              className="p-1 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Refresh"
            >
              <RefreshCw size={14} />
            </button>
          </div>

          <div className="px-4 py-3 max-h-60 overflow-y-auto">
            {isHealthy ? (
              <p className="text-sm text-zinc-400 text-center py-2">
                All models are responding normally.
              </p>
            ) : (
              <div className="flex flex-col gap-2.5">
                {Object.entries(byProvider).map(([provider, provModels]) => (
                  <div key={provider}>
                    <p className="text-xs font-semibold text-zinc-200 mb-1.5 capitalize">{provider}</p>
                    <div className="flex flex-col gap-1">
                      {provModels.map((m) => {
                        const status = STATUS_CONFIG[m.status] || STATUS_CONFIG.unknown
                        const StatusIcon = status.icon
                        const isClearing = clearing === `${m.provider}:${m.model}`
                        return (
                          <div
                            key={`${m.provider}-${m.model}`}
                            className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-zinc-800/50"
                          >
                            <div className="flex items-center gap-1.5 min-w-0">
                              <StatusIcon size={14} style={{ color: status.color }} className="shrink-0" />
                              <span className="font-mono text-xs text-zinc-200 truncate">{m.model}</span>
                            </div>
                            {m.status === 'cooldown' && (
                              <button
                                onClick={() => handleClearCooldown(m.provider, m.model)}
                                disabled={isClearing}
                                className="text-[10px] px-1.5 py-0.5 ml-2 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 transition-colors disabled:opacity-50"
                              >
                                {isClearing ? '...' : 'Clear'}
                              </button>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
