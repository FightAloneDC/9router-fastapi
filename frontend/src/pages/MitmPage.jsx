import { useState, useEffect, useCallback } from 'react'
import {
  Shield,
  ShieldCheck,
  ShieldOff,
  Play,
  Square,
  FileKey,
  Trash2,
  AlertTriangle,
  Globe,
  ArrowUpRight,
  ArrowDownLeft,
  Clock,
  Filter,
  RefreshCw,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Toggle from '../components/ui/Toggle'
import Input from '../components/ui/Input'
import Loading from '../components/ui/Loading'
import { mitmApi } from '../api/mitm'
import { MITM_TOOLS } from '../constants/mitmTools'

export default function MitmPage() {
  const [config, setConfig] = useState(null)
  const [status, setStatus] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [filterTool, setFilterTool] = useState('')
  const [filterDirection, setFilterDirection] = useState('')
  const [baseUrl, setBaseUrl] = useState('')

  // Fetch config, status, and logs
  const fetchData = useCallback(async () => {
    try {
      const [configRes, statusRes, logsRes] = await Promise.all([
        mitmApi.getConfig(),
        mitmApi.getStatus(),
        mitmApi.getLogs({ limit: 50 }),
      ])
      setConfig(configRes.data)
      setStatus(statusRes.data)
      setLogs(logsRes.data)
      setBaseUrl(configRes.data.router_base_url || '')
    } catch (err) {
      console.error('Failed to fetch MITM data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Fetch logs with filters
  const fetchLogs = useCallback(async () => {
    try {
      const params = { limit: 50 }
      if (filterTool) params.tool = filterTool
      if (filterDirection) params.direction = filterDirection
      const res = await mitmApi.getLogs(params)
      setLogs(res.data)
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    }
  }, [filterTool, filterDirection])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  // Start MITM proxy
  const handleStart = async () => {
    setActionLoading('start')
    try {
      await mitmApi.startMitm()
      await fetchData()
    } catch (err) {
      console.error('Failed to start MITM:', err)
    } finally {
      setActionLoading(null)
    }
  }

  // Stop MITM proxy
  const handleStop = async () => {
    setActionLoading('stop')
    try {
      await mitmApi.stopMitm()
      await fetchData()
    } catch (err) {
      console.error('Failed to stop MITM:', err)
    } finally {
      setActionLoading(null)
    }
  }

  // Generate SSL certificate
  const handleGenerateCert = async () => {
    setActionLoading('cert')
    try {
      await mitmApi.generateCert()
      await fetchData()
    } catch (err) {
      console.error('Failed to generate cert:', err)
    } finally {
      setActionLoading(null)
    }
  }

  // Update router base URL
  const handleUpdateBaseUrl = async () => {
    if (baseUrl === config?.router_base_url) return
    try {
      await mitmApi.updateConfig({ router_base_url: baseUrl })
      await fetchData()
    } catch (err) {
      console.error('Failed to update base URL:', err)
    }
  }

  // Toggle DNS for a specific tool
  const handleToggleDns = async (toolKey) => {
    const toolsConfig = { ...(config?.tools_config || {}) }
    const toolCfg = toolsConfig[toolKey] || { dnsEnabled: false, modelMappings: {} }
    toolsConfig[toolKey] = {
      ...toolCfg,
      dnsEnabled: !toolCfg.dnsEnabled,
    }
    try {
      await mitmApi.updateConfig({ tools_config: toolsConfig })
      await fetchData()
    } catch (err) {
      console.error('Failed to toggle DNS:', err)
    }
  }

  // Clear all logs
  const handleClearLogs = async () => {
    try {
      await mitmApi.clearLogs()
      setLogs([])
    } catch (err) {
      console.error('Failed to clear logs:', err)
    }
  }

  // Format timestamp
  const formatTime = (ts) => {
    if (!ts) return '-'
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false }) + '.' +
      String(d.getMilliseconds()).padStart(3, '0')
  }

  // Get status color for direction badge
  const getMethodColor = (method) => {
    const colors = {
      GET: 'success',
      POST: 'primary',
      PUT: 'warning',
      PATCH: 'warning',
      DELETE: 'danger',
    }
    return colors[method] || 'default'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <Loading size="lg" />
      </div>
    )
  }

  const isRunning = status?.running || false

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">MITM Proxy</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Intercept and inspect HTTPS traffic from IDE tools
          </p>
        </div>
      </div>

      {/* Warning Banner */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-600/10 px-4 py-3">
        <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-sm text-amber-200">
          MITM intercepts HTTPS traffic of IDE tools via local CA. May violate ToS. Use at your own risk.
        </p>
      </div>

      {/* Server Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full shrink-0 ${isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500'}`} />
              <h2 className="text-base font-semibold text-zinc-100">
                Proxy Server
              </h2>
              <Badge variant={isRunning ? 'success' : 'default'} size="sm">
                {isRunning ? 'Running' : 'Stopped'}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={isRunning ? 'danger' : 'primary'}
                size="sm"
                onClick={isRunning ? handleStop : handleStart}
                disabled={actionLoading === 'start' || actionLoading === 'stop'}
              >
                {isRunning ? <Square size={14} /> : <Play size={14} />}
                {isRunning
                  ? (actionLoading === 'stop' ? 'Stopping...' : 'Stop')
                  : (actionLoading === 'start' ? 'Starting...' : 'Start')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* SSL Certificate */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {config?.cert_generated ? (
                  <FileKey size={16} className="text-emerald-400" />
                ) : (
                  <FileKey size={16} className="text-zinc-500" />
                )}
                <span className="text-sm text-zinc-300">SSL Certificate</span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateCert}
                disabled={actionLoading === 'cert'}
              >
                <FileKey size={14} />
                {actionLoading === 'cert'
                  ? 'Generating...'
                  : config?.cert_generated
                    ? 'Regenerate Certificate'
                    : 'Generate Certificate'}
              </Button>
              {config?.cert_generated && (
                <p className="text-xs text-emerald-400">Certificate ready</p>
              )}
            </div>

            {/* Router Base URL */}
            <div className="space-y-2">
              <Input
                label="Router Base URL"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                onBlur={handleUpdateBaseUrl}
                placeholder="http://localhost:20128"
              />
            </div>

            {/* Port */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-zinc-300 mb-1.5">
                Proxy Port
              </label>
              <div className="flex items-center gap-2 h-[42px]">
                <div className="px-3.5 py-2.5 rounded-lg border border-zinc-700 bg-zinc-800/50 text-sm text-zinc-100">
                  {config?.port || 443}
                </div>
                <span className="text-xs text-zinc-500">HTTPS</span>
              </div>
            </div>
          </div>

          {/* How it works */}
          <div className="mt-4 rounded-lg bg-zinc-800/40 border border-zinc-800 px-4 py-3">
            <p className="text-xs text-zinc-400 leading-relaxed">
              <span className="font-semibold text-zinc-300">How it works:</span>{' '}
              The MITM proxy acts as a local HTTPS proxy that intercepts traffic from IDE tools.
              Install the generated CA certificate in your system trust store, then configure
              your IDE to use this proxy. All intercepted requests are logged below with full
              headers and body previews for debugging.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Tool Cards Grid */}
      <div>
        <h2 className="text-lg font-semibold text-zinc-100 mb-3">Managed Tools</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(MITM_TOOLS).map(([key, tool]) => {
            const toolCfg = config?.tools_config?.[key] || {}
            const dnsEnabled = toolCfg.dnsEnabled || false
            const isDnsActive = status?.dnsStatus?.[key] || false
            const isCursor = key === 'cursor'

            return (
              <Card
                key={key}
                className={`hover:border-zinc-600/80 transition-colors ${isCursor ? 'opacity-60' : ''}`}
              >
                <CardContent className="p-4">
                  {/* Tool header */}
                  <div className="flex items-center gap-3 mb-3">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold shrink-0"
                      style={{
                        backgroundColor: (tool.color === '#000000' ? '#ffffff' : tool.color) + '20',
                        color: tool.color === '#000000' ? '#e4e4e7' : tool.color,
                      }}
                    >
                      {tool.icon}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-sm font-semibold text-zinc-100 truncate">
                        {tool.name}
                      </h3>
                      <p className="text-xs text-zinc-500">{tool.description}</p>
                    </div>
                  </div>

                  {/* DNS Toggle */}
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs text-zinc-400">DNS Intercept</span>
                    <Toggle
                      checked={dnsEnabled}
                      onChange={() => !isCursor && handleToggleDns(key)}
                      disabled={isCursor}
                    />
                  </div>

                  {/* Status badge */}
                  <div className="mb-3">
                    {isCursor ? (
                      <Badge variant="default" size="sm">Coming Soon</Badge>
                    ) : isDnsActive && isRunning ? (
                      <Badge variant="success" size="sm">Active</Badge>
                    ) : (
                      <Badge variant="default" size="sm">Inactive</Badge>
                    )}
                  </div>

                  {/* Host list */}
                  <div className="space-y-1">
                    {tool.hosts.map((host) => (
                      <div
                        key={host}
                        className="flex items-center gap-1.5 text-[11px] text-zinc-500"
                      >
                        <Globe size={10} className="shrink-0" />
                        <span className="truncate">{host}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      {/* Logs Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-base font-semibold text-zinc-100">
                Traffic Logs
              </h2>
              <Badge variant="default" size="sm">{logs.length}</Badge>
            </div>
            <div className="flex items-center gap-2">
              {/* Tool filter */}
              <select
                value={filterTool}
                onChange={(e) => setFilterTool(e.target.value)}
                className="rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">All tools</option>
                {Object.entries(MITM_TOOLS).map(([key, tool]) => (
                  <option key={key} value={key}>{tool.name}</option>
                ))}
              </select>

              {/* Direction filter */}
              <select
                value={filterDirection}
                onChange={(e) => setFilterDirection(e.target.value)}
                className="rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">All directions</option>
                <option value="request">Requests</option>
                <option value="response">Responses</option>
              </select>

              {/* Refresh */}
              <Button variant="ghost" size="sm" onClick={fetchLogs}>
                <RefreshCw size={14} />
              </Button>

              {/* Clear logs */}
              <Button
                variant="danger"
                size="sm"
                onClick={handleClearLogs}
                disabled={logs.length === 0}
              >
                <Trash2 size={14} />
                Clear
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {logs.length === 0 ? (
            <div className="text-center py-12">
              <Shield size={32} className="mx-auto text-zinc-600 mb-3" />
              <p className="text-sm text-zinc-400">No traffic logs yet</p>
              <p className="text-xs text-zinc-500 mt-1">
                Start the MITM proxy and configure your IDE to see intercepted traffic
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Time
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Tool
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Dir
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Method
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      URL
                    </th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">
                      Latency
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {logs.map((log) => {
                    const toolInfo = MITM_TOOLS[log.tool]
                    return (
                      <tr
                        key={log.id}
                        className="hover:bg-zinc-800/30 transition-colors"
                      >
                        <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <Clock size={11} className="text-zinc-600" />
                            {formatTime(log.timestamp)}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          <Badge variant="default" size="sm">
                            {toolInfo?.name || log.tool}
                          </Badge>
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          {log.direction === 'request' ? (
                            <ArrowUpRight size={14} className="text-blue-400" />
                          ) : (
                            <ArrowDownLeft size={14} className="text-emerald-400" />
                          )}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          {log.method && (
                            <Badge variant={getMethodColor(log.method)} size="sm">
                              {log.method}
                            </Badge>
                          )}
                        </td>
                        <td className="px-4 py-2.5 max-w-xs truncate text-zinc-300 font-mono text-xs">
                          {log.url || '-'}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          {log.status_code && (
                            <Badge
                              variant={
                                log.status_code < 300
                                  ? 'success'
                                  : log.status_code < 400
                                    ? 'warning'
                                    : 'danger'
                              }
                              size="sm"
                            >
                              {log.status_code}
                            </Badge>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right text-xs text-zinc-400 font-mono whitespace-nowrap">
                          {log.latency_ms != null ? `${log.latency_ms}ms` : '-'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
