import { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Trash2,
  Upload,
  Activity,
  Edit2,
  Zap,
  Search,
  CheckSquare,
  Square,
  ToggleLeft,
  ToggleRight,
  Shield,
  AlertCircle,
  CheckCircle2,
  Clock,
  X,
} from 'lucide-react'
import Card, { CardContent } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import { proxyPoolsApi } from '../api/proxyPools'
import { useNotificationStore } from '../stores/notificationStore'

const PROXY_USAGE_FLAGS = [
  ['testConnection', 'Test connection'],
  ['testModel', 'Test model'],
  ['testChat', 'Test chat'],
  ['oauthRefresh', 'OAuth refresh'],
]

const EMPTY_PROXY_USAGE = {
  mode: 'off',
  flags: Object.fromEntries(PROXY_USAGE_FLAGS.map(([key]) => [key, false])),
}

function proxyUsageWithMode(mode, current) {
  return {
    mode,
    flags: { ...EMPTY_PROXY_USAGE.flags, ...(current?.flags || {}) },
  }
}

function ProxyUsageControls({ value, onChange }) {
  const usage = proxyUsageWithMode(value?.mode || 'off', value)

  return (
    <div className="rounded-lg border border-zinc-700/40 bg-zinc-900/50 p-3">
      <p className="mb-2 text-sm font-medium text-zinc-300">Proxy usage</p>
      <div className="flex flex-wrap gap-3">
        {['off', 'selective', 'all'].map((mode) => (
          <label
            key={mode}
            className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-300"
          >
            <input
              type="radio"
              name="default-proxy-usage"
              checked={usage.mode === mode}
              onChange={() => onChange(proxyUsageWithMode(mode, usage))}
              className="border-zinc-600 bg-zinc-800 text-primary-500"
            />
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </label>
        ))}
      </div>
      {usage.mode === 'selective' && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {PROXY_USAGE_FLAGS.map(([key, label]) => (
            <label
              key={key}
              className="flex cursor-pointer items-center gap-2 text-xs text-zinc-400"
            >
              <input
                type="checkbox"
                checked={usage.flags[key] === true}
                onChange={(event) => onChange({
                  ...usage,
                  flags: { ...usage.flags, [key]: event.target.checked },
                })}
                className="rounded border-zinc-600 bg-zinc-800 text-primary-500"
              />
              {label}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ProxyPoolsPage() {
  const [pools, setPools] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selected, setSelected] = useState(new Set())

  // Add/Edit modal
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({
    name: '',
    proxy_url: '',
    no_proxy: '',
    pool_type: 'http',
    is_active: true,
    strict_proxy: false,
    default_proxy_usage: EMPTY_PROXY_USAGE,
  })
  const [saving, setSaving] = useState(false)
  const [applyingUsageId, setApplyingUsageId] = useState(null)
  const addNotification = useNotificationStore((state) => state.addNotification)

  // Batch import modal
  const [showBatchModal, setShowBatchModal] = useState(false)
  const [batchText, setBatchText] = useState('')
  const [importing, setImporting] = useState(false)

  // Testing state
  const [testingIds, setTestingIds] = useState(new Set())

  const fetchPools = useCallback(async () => {
    try {
      const res = await proxyPoolsApi.getAll()
      setPools(res.data)
    } catch (err) {
      console.error('Failed to fetch proxy pools:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPools()
  }, [fetchPools])

  // Filter by search
  const filtered = pools.filter((p) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      p.name.toLowerCase().includes(q) ||
      p.proxy_url.toLowerCase().includes(q) ||
      p.pool_type.toLowerCase().includes(q)
    )
  })

  // Selection helpers
  const allVisibleSelected =
    filtered.length > 0 && filtered.every((p) => selected.has(p.id))

  const toggleSelectAll = () => {
    if (allVisibleSelected) {
      setSelected(new Set())
    } else {
      setSelected(new Set(filtered.map((p) => p.id)))
    }
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // CRUD
  const openAddModal = () => {
    setEditing(null)
    setForm({
      name: '',
      proxy_url: '',
      no_proxy: '',
      pool_type: 'http',
      is_active: true,
      strict_proxy: false,
      default_proxy_usage: EMPTY_PROXY_USAGE,
    })
    setShowModal(true)
  }

  const openEditModal = (pool) => {
    setEditing(pool)
    setForm({
      name: pool.name,
      proxy_url: pool.proxy_url,
      no_proxy: pool.no_proxy || '',
      pool_type: pool.pool_type,
      is_active: pool.is_active,
      strict_proxy: pool.strict_proxy,
      default_proxy_usage: proxyUsageWithMode(
        pool.default_proxy_usage?.mode || 'off',
        pool.default_proxy_usage,
      ),
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.name.trim() || !form.proxy_url.trim()) return
    setSaving(true)
    try {
      if (editing) {
        const res = await proxyPoolsApi.update(editing.id, form)
        setPools((prev) => prev.map((p) => (p.id === editing.id ? res.data : p)))
      } else {
        const res = await proxyPoolsApi.create(form)
        setPools((prev) => [res.data, ...prev])
      }
      setShowModal(false)
    } catch (err) {
      console.error('Failed to save proxy pool:', err)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await proxyPoolsApi.delete(id)
      setPools((prev) => prev.filter((p) => p.id !== id))
      setSelected((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } catch (err) {
      console.error('Failed to delete proxy pool:', err)
    }
  }

  const handleToggleActive = async (pool) => {
    try {
      const res = await proxyPoolsApi.update(pool.id, { is_active: !pool.is_active })
      setPools((prev) => prev.map((p) => (p.id === pool.id ? res.data : p)))
    } catch (err) {
      console.error('Failed to toggle proxy pool:', err)
    }
  }

  const handleApplyUsage = async (pool) => {
    const confirmed = window.confirm(
      'Apply usage settings to all connections using this pool?',
    )
    if (!confirmed) return

    setApplyingUsageId(pool.id)
    try {
      const res = await proxyPoolsApi.applyUsage(pool.id)
      addNotification({
        type: 'success',
        message: `Applied usage settings to ${res.data.updated} connection${
          res.data.updated === 1 ? '' : 's'
        }`,
      })
    } catch (err) {
      console.error('Failed to apply proxy usage settings:', err)
      addNotification({
        type: 'error',
        message: 'Failed to apply usage settings',
      })
    } finally {
      setApplyingUsageId(null)
    }
  }

  // Test proxy
  const handleTest = async (id) => {
    setTestingIds((prev) => new Set(prev).add(id))
    try {
      const res = await proxyPoolsApi.test(id)
      setPools((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, test_status: res.data.status, last_error: res.data.error }
            : p
        )
      )
    } catch (err) {
      console.error('Failed to test proxy pool:', err)
    } finally {
      setTestingIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }

  const handleTestAll = async () => {
    const ids = selected.size > 0 ? Array.from(selected) : pools.map((p) => p.id)
    for (const id of ids) {
      await handleTest(id)
    }
  }

  // Bulk actions
  const handleBulkEnable = async () => {
    for (const id of selected) {
      const pool = pools.find((p) => p.id === id)
      if (pool && !pool.is_active) {
        try {
          await proxyPoolsApi.update(id, { is_active: true })
        } catch (err) {
          console.error('Failed to enable proxy:', err)
        }
      }
    }
    await fetchPools()
  }

  const handleBulkDisable = async () => {
    for (const id of selected) {
      const pool = pools.find((p) => p.id === id)
      if (pool && pool.is_active) {
        try {
          await proxyPoolsApi.update(id, { is_active: false })
        } catch (err) {
          console.error('Failed to disable proxy:', err)
        }
      }
    }
    await fetchPools()
  }

  const handleBulkDelete = async () => {
    for (const id of selected) {
      try {
        await proxyPoolsApi.delete(id)
      } catch (err) {
        console.error('Failed to delete proxy:', err)
      }
    }
    setSelected(new Set())
    await fetchPools()
  }

  // Batch import
  const handleBatchImport = async () => {
    const lines = batchText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length === 0) return

    setImporting(true)
    let created = 0
    for (const line of lines) {
      try {
        let proxyUrl = line
        let name = line

        // Support host:port:user:pass format
        if (!line.includes('://')) {
          const parts = line.split(':')
          if (parts.length === 4) {
            const [host, port, user, pass] = parts
            proxyUrl = `http://${user}:${pass}@${host}:${port}`
            name = `${host}:${port}`
          } else if (parts.length === 2) {
            const [host, port] = parts
            proxyUrl = `http://${host}:${port}`
            name = `${host}:${port}`
          }
        } else {
          // Extract a readable name from URL
          try {
            const url = new URL(line)
            name = url.hostname + (url.port ? ':' + url.port : '')
          } catch {
            name = line.substring(0, 40)
          }
        }

        await proxyPoolsApi.create({
          name,
          proxy_url: proxyUrl,
          pool_type: 'http',
          is_active: true,
          strict_proxy: false,
        })
        created++
      } catch (err) {
        console.error('Failed to import proxy:', line, err)
      }
    }

    setImporting(false)
    setShowBatchModal(false)
    setBatchText('')
    await fetchPools()
  }

  // Status badge helper
  const renderStatus = (pool) => {
    if (testingIds.has(pool.id)) {
      return (
        <Badge variant="info" size="sm">
          <Clock size={10} className="mr-1 animate-spin" />
          Testing
        </Badge>
      )
    }
    switch (pool.test_status) {
      case 'active':
        return (
          <Badge variant="success" size="sm">
            <CheckCircle2 size={10} className="mr-1" />
            Active
          </Badge>
        )
      case 'error':
        return (
          <Badge variant="danger" size="sm">
            <AlertCircle size={10} className="mr-1" />
            Error
          </Badge>
        )
      default:
        return (
          <Badge variant="default" size="sm">
            Unknown
          </Badge>
        )
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Proxy Pools</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {pools.length} proxy{pools.length !== 1 ? 'es' : ''} configured
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowBatchModal(true)}>
            <Upload size={16} />
            Batch Import
          </Button>
          <Button onClick={openAddModal}>
            <Plus size={16} />
            Add Proxy
          </Button>
        </div>
      </div>

      {/* Search & Bulk Actions */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500"
          />
          <input
            type="text"
            placeholder="Search proxies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors hover:border-zinc-600"
          />
        </div>

        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-400">
              {selected.size} selected
            </span>
            <Button variant="outline" size="sm" onClick={handleTestAll}>
              <Zap size={14} />
              Test
            </Button>
            <Button variant="outline" size="sm" onClick={handleBulkEnable}>
              Enable
            </Button>
            <Button variant="outline" size="sm" onClick={handleBulkDisable}>
              Disable
            </Button>
            <Button variant="danger" size="sm" onClick={handleBulkDelete}>
              <Trash2 size={14} />
              Delete
            </Button>
          </div>
        )}

        {selected.size === 0 && pools.length > 0 && (
          <Button variant="outline" size="sm" onClick={handleTestAll}>
            <Activity size={14} />
            Health Check
          </Button>
        )}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-700/50">
                  <th className="px-4 py-3 text-left w-10">
                    <button
                      onClick={toggleSelectAll}
                      className="text-zinc-400 hover:text-zinc-200 cursor-pointer"
                    >
                      {allVisibleSelected ? (
                        <CheckSquare size={16} />
                      ) : (
                        <Square size={16} />
                      )}
                    </button>
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Proxy URL
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Active
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {filtered.map((pool) => (
                  <tr
                    key={pool.id}
                    className="hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleSelect(pool.id)}
                        className="text-zinc-400 hover:text-zinc-200 cursor-pointer"
                      >
                        {selected.has(pool.id) ? (
                          <CheckSquare size={16} className="text-primary-400" />
                        ) : (
                          <Square size={16} />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {pool.strict_proxy && (
                          <Shield
                            size={14}
                            className="text-amber-400 shrink-0"
                            title="Strict proxy"
                          />
                        )}
                        <span className="font-medium text-zinc-100 truncate max-w-[200px]">
                          {pool.name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-zinc-400 font-mono text-xs truncate block max-w-[300px]">
                        {pool.proxy_url.replace(/\/\/([^:]+):([^@]+)@/, '//$1:***@')}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="default" size="sm">
                        {pool.pool_type.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">{renderStatus(pool)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleActive(pool)}
                        className="cursor-pointer"
                        title={pool.is_active ? 'Deactivate' : 'Activate'}
                      >
                        {pool.is_active ? (
                          <ToggleRight
                            size={20}
                            className="text-emerald-400"
                          />
                        ) : (
                          <ToggleLeft size={20} className="text-zinc-500" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleTest(pool.id)}
                          disabled={testingIds.has(pool.id)}
                          className="p-1.5 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer disabled:opacity-50"
                          title="Test connectivity"
                        >
                          <Zap size={14} />
                        </button>
                        <button
                          onClick={() => openEditModal(pool)}
                          className="p-1.5 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                          title="Edit"
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(pool.id)}
                          className="p-1.5 rounded-lg hover:bg-red-600/20 text-zinc-500 hover:text-red-400 transition-colors cursor-pointer"
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {filtered.length === 0 && (
            <div className="text-center py-12">
              <Activity size={32} className="mx-auto text-zinc-600 mb-3" />
              <p className="text-sm text-zinc-400">No proxy pools found</p>
              <p className="text-xs text-zinc-500 mt-1">
                Add a proxy or import in bulk to get started
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Modal */}
      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editing ? 'Edit Proxy Pool' : 'Add Proxy Pool'}
      >
        <div className="space-y-4">
          <Input
            label="Name"
            placeholder="e.g. US Residential, EU Datacenter"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <Input
            label="Proxy URL"
            placeholder="http://user:pass@host:port"
            value={form.proxy_url}
            onChange={(e) => setForm({ ...form, proxy_url: e.target.value })}
          />
          <Input
            label="No Proxy (optional)"
            placeholder="Comma-separated hosts to bypass, e.g. localhost,10.0.0.0/8"
            value={form.no_proxy}
            onChange={(e) => setForm({ ...form, no_proxy: e.target.value })}
          />

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              Type
            </label>
            <div className="flex gap-2">
              {['http', 'socks5', 'vercel'].map((t) => (
                <button
                  key={t}
                  onClick={() => setForm({ ...form, pool_type: t })}
                  className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors cursor-pointer ${
                    form.pool_type === t
                      ? 'border-primary-500 bg-primary-600/20 text-primary-300'
                      : 'border-zinc-700 bg-zinc-800/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200'
                  }`}
                >
                  {t.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-300">Active</p>
              <p className="text-xs text-zinc-500">Enable this proxy pool</p>
            </div>
            <Toggle
              checked={form.is_active}
              onChange={(val) => setForm({ ...form, is_active: val })}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-zinc-300">Strict Proxy</p>
              <p className="text-xs text-zinc-500">
                Fail requests if proxy is down
              </p>
            </div>
            <Toggle
              checked={form.strict_proxy}
              onChange={(val) => setForm({ ...form, strict_proxy: val })}
            />
          </div>

          <ProxyUsageControls
            value={form.default_proxy_usage}
            onChange={(default_proxy_usage) => setForm({
              ...form,
              default_proxy_usage,
            })}
          />

          {editing && (
            <div className="rounded-lg border border-zinc-700/40 p-3">
              <p className="text-xs text-zinc-500">
                Save changes before applying this template.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => handleApplyUsage(editing)}
                disabled={applyingUsageId === editing.id}
              >
                {applyingUsageId === editing.id
                  ? 'Applying...'
                  : 'Apply usage settings to all connections using this pool'}
              </Button>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!form.name.trim() || !form.proxy_url.trim() || saving}
            >
              {saving
                ? 'Saving...'
                : editing
                  ? 'Save Changes'
                  : 'Add Proxy'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Batch Import Modal */}
      <Modal
        isOpen={showBatchModal}
        onClose={() => {
          setShowBatchModal(false)
          setBatchText('')
        }}
        title="Batch Import Proxies"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              Proxy List
            </label>
            <p className="text-xs text-zinc-500 mb-2">
              One proxy per line. Supported formats:
            </p>
            <div className="text-xs text-zinc-500 mb-3 space-y-1 font-mono bg-zinc-800/50 rounded-lg p-3">
              <p>http://user:pass@host:port</p>
              <p>socks5://user:pass@host:port</p>
              <p>host:port:user:pass</p>
              <p>host:port</p>
            </div>
            <textarea
              rows={8}
              placeholder="http://user:pass@proxy1.example.com:8080&#10;socks5://user:pass@proxy2.example.com:1080&#10;192.168.1.100:3128:user:pass"
              value={batchText}
              onChange={(e) => setBatchText(e.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors hover:border-zinc-600 font-mono"
            />
          </div>

          <div className="flex justify-between items-center pt-2">
            <span className="text-xs text-zinc-500">
              {batchText.split('\n').filter((l) => l.trim()).length} proxy
              {batchText.split('\n').filter((l) => l.trim()).length !== 1
                ? 'es'
                : ''}{' '}
              to import
            </span>
            <div className="flex gap-3">
              <Button
                variant="ghost"
                onClick={() => {
                  setShowBatchModal(false)
                  setBatchText('')
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleBatchImport}
                disabled={
                  !batchText.trim() ||
                  importing ||
                  batchText.split('\n').filter((l) => l.trim()).length === 0
                }
              >
                {importing ? 'Importing...' : 'Import'}
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
