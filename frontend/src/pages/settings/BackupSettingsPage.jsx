import { useEffect, useMemo, useState } from 'react'
import { Database, Download, Search, Upload, X } from 'lucide-react'
import { settingsApi } from '../../api/settings'
import useCatalogStore from '../../stores/catalogStore'
import { Section } from './settingsUi'

const HEALTH_OPTIONS = [
  { value: '', label: 'Any health tier' },
  { value: 'healthy', label: 'Healthy only' },
  { value: 'rate_limited', label: 'Rate limited' },
  { value: 'cooldown', label: 'Cooldown' },
  { value: 'exhausted', label: 'Exhausted' },
  { value: 'dead', label: 'Dead / revoked' },
]

const STATUS_OPTIONS = [
  { value: '', label: 'Any test status' },
  { value: 'connected', label: 'Connected' },
  { value: 'error', label: 'Error' },
  { value: 'unavailable', label: 'Unavailable' },
  { value: 'untested', label: 'Untested' },
  { value: 'unknown', label: 'Unknown' },
]

const selectClass =
  'rounded-md border border-zinc-700 bg-zinc-800/50 px-2 py-1.5 text-xs text-zinc-200 focus:outline-none focus:ring-1 focus:ring-primary-500 w-full'

function TransferPanel({ variant, title, description, children }) {
  const isImport = variant === 'import'
  const Icon = isImport ? Upload : Download
  const panelClass = isImport
    ? 'border-amber-500/40 bg-amber-500/5'
    : 'border-emerald-500/40 bg-emerald-500/5'
  const iconClass = isImport ? 'text-amber-400' : 'text-emerald-400'
  const badgeClass = isImport
    ? 'bg-amber-500/15 text-amber-300'
    : 'bg-emerald-500/15 text-emerald-300'

  return (
    <div className={`rounded-lg border p-4 space-y-3 ${panelClass}`}>
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg bg-zinc-900/60 shrink-0 ${iconClass}`}>
          <Icon size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-zinc-100">{title}</p>
            <span className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded font-medium ${badgeClass}`}>
              {isImport ? 'Import' : 'Export'}
            </span>
          </div>
          {description && (
            <p className="text-xs text-zinc-500 mt-1">{description}</p>
          )}
        </div>
      </div>
      {children}
    </div>
  )
}

export default function BackupSettingsPage() {
  const catalog = useCatalogStore((s) => s.providers)
  const fetchCatalog = useCatalogStore((s) => s.fetchCatalog)

  const [dbLoading, setDbLoading] = useState(false)
  const [dbStatus, setDbStatus] = useState({ type: '', message: '' })

  const [selectedProviders, setSelectedProviders] = useState([])
  const [health, setHealth] = useState('')
  const [testStatus, setTestStatus] = useState('')
  const [isActive, setIsActive] = useState('')
  const [includeCatalog, setIncludeCatalog] = useState(true)
  const [includeQuota, setIncludeQuota] = useState(true)
  const [importMode, setImportMode] = useState('merge_providers')
  const [providerSearch, setProviderSearch] = useState('')

  useEffect(() => {
    fetchCatalog()
  }, [fetchCatalog])

  const providerOptions = useMemo(() => {
    return Object.entries(catalog)
      .map(([id, meta]) => ({
        id,
        label: meta?.name || id,
        alias: meta?.alias || '',
      }))
      .sort((a, b) => a.label.localeCompare(b.label))
  }, [catalog])

  const filteredProviderOptions = useMemo(() => {
    const q = providerSearch.trim().toLowerCase()
    if (!q) return providerOptions
    return providerOptions.filter(
      (p) =>
        p.label.toLowerCase().includes(q) ||
        p.id.toLowerCase().includes(q) ||
        p.alias.toLowerCase().includes(q),
    )
  }, [providerOptions, providerSearch])

  const selectVisibleProviders = () => {
    const ids = filteredProviderOptions.map((p) => p.id)
    setSelectedProviders((prev) => [...new Set([...prev, ...ids])])
  }

  const clearProviderSelection = () => setSelectedProviders([])

  const downloadJson = (data, filename) => {
    const content = JSON.stringify(data, null, 2)
    const blob = new Blob([content], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const buildExportParams = () => {
    const params = {
      include_catalog: includeCatalog,
      include_quota: includeQuota,
    }
    if (selectedProviders.length > 0) {
      params.providers = selectedProviders.join(',')
    }
    if (health) params.health = health
    if (testStatus) params.test_status = testStatus
    if (isActive === 'true') params.is_active = true
    if (isActive === 'false') params.is_active = false
    return params
  }

  const toggleProvider = (id) => {
    setSelectedProviders((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    )
  }

  const handleExportDatabase = async () => {
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await settingsApi.exportDatabase()
      const stamp = new Date().toISOString().replace(/[.:]/g, '-')
      downloadJson(res.data, `9router-backup-${stamp}.json`)
      setDbStatus({ type: 'success', message: 'Full backup downloaded' })
    } catch {
      setDbStatus({ type: 'error', message: 'Failed to export database' })
    } finally {
      setDbLoading(false)
    }
  }

  const handleExportAllConnections = async () => {
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await settingsApi.exportConnections({
        include_catalog: true,
        include_quota: true,
      })
      const stamp = new Date().toISOString().replace(/[.:]/g, '-')
      downloadJson(res.data, `9router-connections-${stamp}.json`)
      setDbStatus({ type: 'success', message: 'All connections exported' })
    } catch {
      setDbStatus({ type: 'error', message: 'Failed to export connections' })
    } finally {
      setDbLoading(false)
    }
  }

  const handleExportSelective = async () => {
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await settingsApi.exportConnections(buildExportParams())
      const stamp = new Date().toISOString().replace(/[.:]/g, '-')
      const suffix =
        selectedProviders.length > 0
          ? selectedProviders.slice(0, 3).join('_')
          : 'filtered'
      downloadJson(res.data, `9router-connections-${suffix}-${stamp}.json`)
      const count =
        res.data?.tables?.provider_connections?.length ?? 0
      setDbStatus({
        type: 'success',
        message: `Exported ${count} connection(s)`,
      })
    } catch (err) {
      setDbStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Selective export failed',
      })
    } finally {
      setDbLoading(false)
    }
  }

  const importPayload = async (file, importer, params = {}) => {
    const raw = await file.text()
    const payload = JSON.parse(raw)
    const mode = payload.import_mode || params.import_mode
    const query = mode ? { import_mode: mode } : {}
    return importer(payload, query)
  }

  const handleImportDatabase = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await importPayload(file, settingsApi.importDatabase)
      if (res.data?.success) {
        setDbStatus({ type: 'success', message: 'Full database imported' })
      }
    } catch (err) {
      setDbStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to import database',
      })
    } finally {
      setDbLoading(false)
      event.target.value = ''
    }
  }

  const handleImportConnections = async (event, mode) => {
    const file = event.target.files?.[0]
    if (!file) return
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await importPayload(
        file,
        settingsApi.importConnections,
        { import_mode: mode },
      )
      if (res.data?.success) {
        setDbStatus({
          type: 'success',
          message: `Imported (${res.data.import_mode || mode})`,
        })
      }
    } catch (err) {
      setDbStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to import connections',
      })
    } finally {
      setDbLoading(false)
      event.target.value = ''
    }
  }

  const exportBtnClass =
    'px-3 py-2 text-sm rounded-lg border border-emerald-600/50 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/20 transition-colors disabled:opacity-50'
  const importBtnClass =
    'px-3 py-2 text-sm rounded-lg border border-amber-600/50 bg-amber-500/10 text-amber-100 hover:bg-amber-500/20 transition-colors cursor-pointer disabled:opacity-50'

  return (
    <>
      <Section
        icon={Database}
        title="Full database"
        description="Complete snapshot for disaster recovery or moving the entire instance"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TransferPanel
            variant="export"
            title="Download backup"
            description="Saves every table to a JSON file on your machine."
          >
            <button
              onClick={handleExportDatabase}
              disabled={dbLoading}
              className={exportBtnClass}
            >
              Download full backup
            </button>
          </TransferPanel>

          <TransferPanel
            variant="import"
            title="Restore backup"
            description="Replaces matching tables. An auto-backup is created first."
          >
            <p className="text-xs text-amber-200/80">
              Destructive — overwrites data on this instance.
            </p>
            <label className={importBtnClass}>
              Choose backup file (.json)
              <input
                type="file"
                accept=".json"
                className="hidden"
                onChange={handleImportDatabase}
              />
            </label>
          </TransferPanel>
        </div>
      </Section>

      <Section
        icon={Database}
        title="All connections"
        description="Every provider connection, catalog row, quota cache, pools, and nodes"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TransferPanel
            variant="export"
            title="Export every connection"
            description="Does not include dashboard users, settings, or usage history."
          >
            <button
              onClick={handleExportAllConnections}
              disabled={dbLoading}
              className={exportBtnClass}
            >
              Export all connections
            </button>
          </TransferPanel>

          <TransferPanel
            variant="import"
            title="Replace all connections"
            description="Wipes every connection-related table, then restores from file."
          >
            <p className="text-xs text-amber-200/80">
              Always uses replace-all mode. Other providers on this machine are
              removed before import.
            </p>
            <label className={importBtnClass}>
              Choose connections file (.json)
              <input
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) =>
                  handleImportConnections(e, 'replace_all')
                }
              />
            </label>
          </TransferPanel>
        </div>
      </Section>

      <Section
        icon={Database}
        title="Selective export & import"
        description="Filter connections by provider, health, or status"
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TransferPanel
            variant="export"
            title="Filtered export"
            description="Verbatim row export for migration — not provider bulk-add."
          >
            <p className="text-xs text-zinc-500">
              Related proxy pools, nodes, catalog, and quota rows are included
              automatically.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <p className="text-xs text-zinc-500 mb-1">Health tier</p>
                <select
                  value={health}
                  onChange={(e) => setHealth(e.target.value)}
                  className={selectClass}
                >
                  {HEALTH_OPTIONS.map((o) => (
                    <option key={o.value || 'any'} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Test status</p>
                <select
                  value={testStatus}
                  onChange={(e) => setTestStatus(e.target.value)}
                  className={selectClass}
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value || 'any'} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Active state</p>
                <select
                  value={isActive}
                  onChange={(e) => setIsActive(e.target.value)}
                  className={selectClass}
                >
                  <option value="">Any</option>
                  <option value="true">Active only</option>
                  <option value="false">Inactive only</option>
                </select>
              </div>
              <div className="flex flex-col gap-2 text-xs text-zinc-400">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeCatalog}
                    onChange={(e) => setIncludeCatalog(e.target.checked)}
                  />
                  Include model catalog & aliases
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={includeQuota}
                    onChange={(e) => setIncludeQuota(e.target.checked)}
                  />
                  Include quota cache
                </label>
              </div>
            </div>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <p className="text-xs text-zinc-500">
                  Providers (empty = all matching filters above)
                </p>
                {providerOptions.length > 0 && (
                  <span className="text-[11px] text-zinc-600">
                    {filteredProviderOptions.length} of {providerOptions.length}
                  </span>
                )}
              </div>
              <div className="relative mb-2">
                <Search
                  size={14}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500"
                />
                <input
                  type="text"
                  value={providerSearch}
                  onChange={(e) => setProviderSearch(e.target.value)}
                  placeholder="Search name, id, or alias..."
                  className="w-full rounded-md border border-zinc-700 bg-zinc-800/50 pl-8 pr-8 py-2 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
                {providerSearch && (
                  <button
                    type="button"
                    onClick={() => setProviderSearch('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                    aria-label="Clear search"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
              {filteredProviderOptions.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  <button
                    type="button"
                    onClick={selectVisibleProviders}
                    className="text-[11px] text-primary-400 hover:text-primary-300"
                  >
                    Select visible
                  </button>
                  {selectedProviders.length > 0 && (
                    <button
                      type="button"
                      onClick={clearProviderSelection}
                      className="text-[11px] text-zinc-500 hover:text-zinc-300"
                    >
                      Clear selection
                    </button>
                  )}
                </div>
              )}
              <div
                className="max-h-64 overflow-y-auto rounded-lg border border-zinc-800 p-2 space-y-1"
              >
                {providerOptions.length === 0 ? (
                  <p className="text-xs text-zinc-500">Loading providers...</p>
                ) : filteredProviderOptions.length === 0 ? (
                  <p className="text-xs text-zinc-500 px-2 py-1">
                    No providers match &quot;{providerSearch.trim()}&quot;
                  </p>
                ) : (
                  filteredProviderOptions.map((p) => (
                    <label
                      key={p.id}
                      className="flex items-center gap-2 text-xs text-zinc-300 hover:bg-zinc-800/50 rounded px-2 py-1"
                    >
                      <input
                        type="checkbox"
                        checked={selectedProviders.includes(p.id)}
                        onChange={() => toggleProvider(p.id)}
                      />
                      <span className="truncate">{p.label}</span>
                      <span className="text-zinc-600 font-mono truncate">
                        {p.id}
                      </span>
                    </label>
                  ))
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-2 items-center">
              <button
                onClick={handleExportSelective}
                disabled={dbLoading}
                className={exportBtnClass}
              >
                Export with filters
              </button>
              {selectedProviders.length > 0 && (
                <span className="text-xs text-zinc-500">
                  {selectedProviders.length} provider(s) selected
                </span>
              )}
            </div>
          </TransferPanel>

          <TransferPanel
            variant="import"
            title="Restore connection file"
            description="Pick how providers in the file interact with existing data."
          >
            <p className="text-xs text-amber-200/80">
              Import only connection payloads — not full database backups.
            </p>

            <div className="flex flex-col gap-2 text-xs text-zinc-300">
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="importMode"
                  value="merge_providers"
                  checked={importMode === 'merge_providers'}
                  onChange={() => setImportMode('merge_providers')}
                />
                <span>
                  <strong>Merge providers</strong> — only replace providers in
                  the file; others on this machine stay untouched
                </span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="radio"
                  name="importMode"
                  value="replace_all"
                  checked={importMode === 'replace_all'}
                  onChange={() => setImportMode('replace_all')}
                />
                <span>
                  <strong>Replace all connections</strong> — wipe every
                  connection table before import
                </span>
              </label>
            </div>

            <label className={importBtnClass}>
              Choose connections file (.json)
              <input
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) =>
                  handleImportConnections(e, importMode)
                }
              />
            </label>
          </TransferPanel>
        </div>
      </Section>

      {dbStatus.message && (
        <p
          className={`text-xs ${
            dbStatus.type === 'error' ? 'text-red-400' : 'text-emerald-400'
          }`}
        >
          {dbStatus.message}
        </p>
      )}
    </>
  )
}
