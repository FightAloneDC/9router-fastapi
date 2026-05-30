import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal, ArrowDownToLine, Trash2, Search, Wifi, WifiOff, RefreshCw } from 'lucide-react'
import { consoleApi } from '../api/console'
import { useAuthStore } from '../stores/authStore'

const LEVEL_COLORS = {
  INFO: 'text-green-400',
  WARN: 'text-yellow-400',
  ERROR: 'text-red-400',
  DEBUG: 'text-gray-400',
}

const LEVEL_BG = {
  INFO: 'bg-green-500/20',
  WARN: 'bg-yellow-500/20',
  ERROR: 'bg-red-500/20',
  DEBUG: 'bg-gray-500/20',
}

const MAX_ENTRIES = 500

export default function ConsoleLogPage() {
  const [logs, setLogs] = useState([])
  const [autoScroll, setAutoScroll] = useState(true)
  const [levelFilter, setLevelFilter] = useState('ALL')
  const [searchText, setSearchText] = useState('')
  const [connected, setConnected] = useState(false)
  const [usePolling, setUsePolling] = useState(false)
  const endRef = useRef(null)
  const containerRef = useRef(null)
  const wsRef = useRef(null)
  const token = useAuthStore((s) => s.token)

  const addEntries = useCallback((entries) => {
    setLogs((prev) => {
      const next = [...prev, ...entries]
      return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
    })
  }, [])

  // WebSocket connection
  useEffect(() => {
    if (!token) return

    let ws
    let retryTimer

    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${proto}//${host}/api/console/ws`

      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setUsePolling(false)
      }

      ws.onmessage = (event) => {
        try {
          const entry = JSON.parse(event.data)
          addEntries([entry])
        } catch {
          // ignore parse errors
        }
      }

      ws.onclose = () => {
        setConnected(false)
        // Fall back to polling
        setUsePolling(true)
        retryTimer = setTimeout(connect, 5000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    return () => {
      clearTimeout(retryTimer)
      if (ws) {
        ws.onclose = null
        ws.close()
      }
    }
  }, [token, addEntries])

  // Polling fallback
  useEffect(() => {
    if (!usePolling) return

    const poll = async () => {
      try {
        const res = await consoleApi.getLogs(100)
        if (res.data?.logs) {
          setLogs((prev) => {
            const existing = new Set(prev.map((e) => e.timestamp + e.message))
            const newEntries = res.data.logs.filter(
              (e) => !existing.has(e.timestamp + e.message)
            )
            if (newEntries.length === 0) return prev
            const next = [...prev, ...newEntries]
            return next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next
          })
        }
      } catch {
        // ignore
      }
    }

    const interval = setInterval(poll, 3000)
    poll()
    return () => clearInterval(interval)
  }, [usePolling])

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const filteredLogs = logs.filter((entry) => {
    if (levelFilter !== 'ALL' && entry.level !== levelFilter) return false
    if (searchText && !entry.message.toLowerCase().includes(searchText.toLowerCase())) return false
    return true
  })

  const handleClear = () => setLogs([])

  const formatTime = (ts) => {
    try {
      const d = new Date(ts)
      return d.toLocaleTimeString('en-US', { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0')
    } catch {
      return ts
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-zinc-950 text-zinc-200 font-mono text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-3">
          <Terminal className="w-5 h-5 text-emerald-400" />
          <h1 className="text-lg font-semibold text-zinc-100">Live Console</h1>
          <span className="text-xs text-zinc-500">
            {filteredLogs.length} / {logs.length} entries
          </span>
          {connected ? (
            <span className="flex items-center gap-1 text-xs text-green-400">
              <Wifi className="w-3 h-3" /> Live
            </span>
          ) : usePolling ? (
            <span className="flex items-center gap-1 text-xs text-yellow-400">
              <RefreshCw className="w-3 h-3 animate-spin" /> Polling
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-400">
              <WifiOff className="w-3 h-3" /> Disconnected
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Level filter */}
          {['ALL', 'INFO', 'WARN', 'ERROR'].map((level) => (
            <button
              key={level}
              onClick={() => setLevelFilter(level)}
              className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
                levelFilter === level
                  ? 'bg-zinc-700 text-zinc-100'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800'
              }`}
            >
              {level}
            </button>
          ))}
          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1.5 rounded transition-colors ${
              autoScroll ? 'bg-emerald-600/30 text-emerald-400' : 'text-zinc-500 hover:bg-zinc-800'
            }`}
            title="Auto-scroll"
          >
            <ArrowDownToLine className="w-4 h-4" />
          </button>
          {/* Clear */}
          <button
            onClick={handleClear}
            className="p-1.5 rounded text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 transition-colors"
            title="Clear logs"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="px-4 py-2 border-b border-zinc-800/50">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Filter logs..."
            className="w-full pl-8 pr-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600"
          />
        </div>
      </div>

      {/* Log entries */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-2">
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-600">
            <div className="text-center">
              <Terminal className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>No log entries yet</p>
              <p className="text-xs mt-1">Logs will appear here as requests are made</p>
            </div>
          </div>
        ) : (
          filteredLogs.map((entry, i) => (
            <div
              key={i}
              className="flex items-start gap-2 py-0.5 hover:bg-zinc-900/50 group"
            >
              <span className="text-zinc-600 whitespace-nowrap min-w-[100px]">
                {formatTime(entry.timestamp)}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold whitespace-nowrap ${LEVEL_BG[entry.level] || ''} ${LEVEL_COLORS[entry.level] || 'text-zinc-400'}`}
              >
                {entry.level}
              </span>
              <span className="text-zinc-500 whitespace-nowrap min-w-[40px]">
                [{entry.source}]
              </span>
              <span className="text-zinc-300 break-all">{entry.message}</span>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  )
}
