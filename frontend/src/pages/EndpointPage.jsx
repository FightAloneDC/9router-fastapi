import { useState, useEffect, useCallback } from 'react'
import { Globe, Copy, Plus, Trash2, Check, Key, Shield, ShieldOff, Eye, EyeOff } from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import { endpointsApi } from '../api/endpoints'

const ENDPOINT_URL = `${window.location.protocol}//${window.location.host}/v1/chat/completions`

function maskKey(key) {
  if (!key || key.length < 12) return key
  return key.slice(0, 8) + '...' + key.slice(-4)
}

export default function EndpointPage() {
  const [keys, setKeys] = useState([])
  const [settings, setSettings] = useState({ requireApiKey: false, requireLogin: true })
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [newKeyName, setNewKeyName] = useState('')
  const [creating, setCreating] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [visibleKeys, setVisibleKeys] = useState(new Set())
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const [keysRes, settingsRes] = await Promise.all([
        endpointsApi.getKeys(),
        endpointsApi.getSettings(),
      ])
      setKeys(keysRes.data.keys)
      setSettings(settingsRes.data)
    } catch (err) {
      console.error('Failed to fetch endpoint data:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleCopyUrl = async () => {
    try {
      await navigator.clipboard.writeText(ENDPOINT_URL)
      setCopiedUrl(true)
      setTimeout(() => setCopiedUrl(false), 2000)
    } catch {
      // Fallback for non-HTTPS
      const textarea = document.createElement('textarea')
      textarea.value = ENDPOINT_URL
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopiedUrl(true)
      setTimeout(() => setCopiedUrl(false), 2000)
    }
  }

  const handleCopyKey = async (key) => {
    try {
      await navigator.clipboard.writeText(key)
      setCopiedId(key)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = key
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      setCopiedId(key)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  const handleCreateKey = async () => {
    setCreating(true)
    try {
      const res = await endpointsApi.createKey(newKeyName.trim() || null)
      setNewlyCreatedKey(res.data)
      setNewKeyName('')
      setShowAddModal(false)
      await fetchData()
    } catch (err) {
      console.error('Failed to create key:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteKey = async (id) => {
    try {
      await endpointsApi.deleteKey(id)
      setKeys((prev) => prev.filter((k) => k.id !== id))
    } catch (err) {
      console.error('Failed to delete key:', err)
    }
  }

  const handleToggleKey = async (id) => {
    try {
      const res = await endpointsApi.toggleKey(id)
      setKeys((prev) => prev.map((k) => (k.id === id ? res.data : k)))
    } catch (err) {
      console.error('Failed to toggle key:', err)
    }
  }

  const handleToggleSetting = async (field, value) => {
    try {
      const res = await endpointsApi.updateSettings({ [field]: value })
      setSettings(res.data)
    } catch (err) {
      console.error('Failed to update settings:', err)
    }
  }

  const toggleKeyVisibility = (key) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
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
      {/* Dismiss newly created key banner */}
      {newlyCreatedKey && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-600/10 p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <Check size={18} className="text-emerald-400 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-emerald-300">API key created successfully</p>
                <p className="mt-1 text-xs text-zinc-400">Copy this key now — it will not be shown again in full.</p>
                <div className="mt-2 flex items-center gap-2">
                  <code className="text-xs bg-zinc-800 rounded px-2 py-1 text-zinc-200 break-all">{newlyCreatedKey.key}</code>
                  <button
                    onClick={() => handleCopyKey(newlyCreatedKey.key)}
                    className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                    title="Copy key"
                  >
                    {copiedId === newlyCreatedKey.key ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                  </button>
                </div>
              </div>
            </div>
            <button
              onClick={() => setNewlyCreatedKey(null)}
              className="text-zinc-500 hover:text-zinc-300 transition-colors cursor-pointer text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Endpoint URL */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 flex items-center justify-center">
              <Globe size={16} className="text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-zinc-100">Endpoint URL</h3>
              <p className="text-xs text-zinc-500">Use this URL to send requests to 9Router</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <div className="flex-1 min-w-0 bg-zinc-800/60 rounded-lg px-4 py-3 border border-zinc-700/50">
              <code className="text-sm text-zinc-200 break-all">{ENDPOINT_URL}</code>
            </div>
            <Button variant="secondary" size="sm" onClick={handleCopyUrl} className="shrink-0">
              {copiedUrl ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
              {copiedUrl ? 'Copied' : 'Copy'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-amber-600/20 flex items-center justify-center">
                <Key size={16} className="text-amber-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-zinc-100">API Keys</h3>
                <p className="text-xs text-zinc-500">Manage keys for authenticating API requests</p>
              </div>
            </div>
            <Button size="sm" onClick={() => setShowAddModal(true)}>
              <Plus size={14} />
              Add Key
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {keys.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <Key size={32} className="mx-auto text-zinc-600 mb-3" />
              <p className="text-sm text-zinc-400">No API keys yet</p>
              <p className="text-xs text-zinc-500 mt-1">Create a key to authenticate your API requests</p>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {keys.map((apiKey) => (
                <div
                  key={apiKey.id}
                  className="flex items-center justify-between px-6 py-4 hover:bg-zinc-800/30 transition-colors"
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200 truncate">
                          {apiKey.name || 'Unnamed Key'}
                        </span>
                        <Badge variant={apiKey.is_active ? 'success' : 'danger'} size="sm">
                          {apiKey.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1.5 mt-1">
                        <code className="text-xs text-zinc-500">
                          {visibleKeys.has(apiKey.key) ? apiKey.key : maskKey(apiKey.key)}
                        </code>
                        <button
                          onClick={() => toggleKeyVisibility(apiKey.key)}
                          className="p-0.5 rounded text-zinc-600 hover:text-zinc-400 transition-colors cursor-pointer"
                          title={visibleKeys.has(apiKey.key) ? 'Hide key' : 'Show key'}
                        >
                          {visibleKeys.has(apiKey.key) ? <EyeOff size={12} /> : <Eye size={12} />}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    <button
                      onClick={() => handleCopyKey(apiKey.key)}
                      className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
                      title="Copy key"
                    >
                      {copiedId === apiKey.key ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
                    </button>
                    <Toggle
                      checked={apiKey.is_active}
                      onChange={() => handleToggleKey(apiKey.id)}
                    />
                    <button
                      onClick={() => handleDeleteKey(apiKey.id)}
                      className="p-2 rounded-lg hover:bg-red-600/20 text-zinc-400 hover:text-red-400 transition-colors cursor-pointer"
                      title="Delete key"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-600/20 flex items-center justify-center">
              <Shield size={16} className="text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-zinc-100">Security Settings</h3>
              <p className="text-xs text-zinc-500">Configure authentication requirements</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-zinc-200">Require API Key</p>
                <p className="text-xs text-zinc-500 mt-0.5">
                  When enabled, requests must include a valid API key in the Authorization header
                </p>
              </div>
              <Toggle
                checked={settings.requireApiKey}
                onChange={(val) => handleToggleSetting('requireApiKey', val)}
              />
            </div>
            <div className="border-t border-zinc-800" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-zinc-200">Require Login</p>
                <p className="text-xs text-zinc-500 mt-0.5">
                  When enabled, users must log in to access the dashboard
                </p>
              </div>
              <Toggle
                checked={settings.requireLogin}
                onChange={(val) => handleToggleSetting('requireLogin', val)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Add Key Modal */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false)
          setNewKeyName('')
        }}
        title="Create API Key"
      >
        <div className="space-y-4">
          <Input
            label="Key Name (optional)"
            placeholder="e.g. Production, Development, CI/CD"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !creating) handleCreateKey()
            }}
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="ghost"
              onClick={() => {
                setShowAddModal(false)
                setNewKeyName('')
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleCreateKey} disabled={creating}>
              {creating ? 'Creating...' : 'Create Key'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
