import { useState, useEffect } from 'react'
import { Loader2, Lock, AlertCircle, CheckCircle2 } from 'lucide-react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import Input from './ui/Input'
import Badge from './ui/Badge'

export default function OAuthEditModal({ isOpen, connection, proxyPools = [], onClose, onSave }) {
  const [name, setName] = useState('')
  const [priority, setPriority] = useState(0)
  const [proxyPoolId, setProxyPoolId] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Determine connection type label — check loginMethod from providerSpecificData (for qoder dual-mode)
  const psd = connection?.providerSpecificData || connection?.provider_specific || {}
  const isPat = psd.loginMethod === 'pat' || connection?.auth_type === 'apikey'
  const modalTitle = isPat ? 'Edit PAT Connection' : 'Edit OAuth Connection'
  const typeLabel = isPat ? 'PAT Connection' : 'OAuth Connection'

  // Reset form when connection changes
  useEffect(() => {
    if (isOpen && connection) {
      setName(connection.name || '')
      setPriority(connection.priority ?? 0)
      setProxyPoolId(connection.proxy_pool_id || '')
      setError('')
    }
  }, [isOpen, connection])

  const handleSave = async () => {
    if (!connection) return

    setSaving(true)
    setError('')
    try {
      const { providersApi } = await import('../api/providers')
      await providersApi.updateProvider(connection.id, {
        name: name.trim() || connection.name,
        priority,
        proxyPoolId: proxyPoolId || null,
      })
      onSave()
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to save'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  if (!connection) return null

  const providerSpecific = connection.providerSpecificData || connection.provider_specific || {}
  const expiresAt = providerSpecific.expiresAt
  const lastError = providerSpecific.lastError
  const isExpired = expiresAt && new Date(expiresAt).getTime() < Date.now()

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={modalTitle}
      className="max-w-md"
    >
      <div className="space-y-4">
        {/* Connection type indicator */}
        <div className="flex items-center gap-2 p-3 rounded-lg bg-zinc-900/50 border border-zinc-700/40">
          <Lock size={16} className="text-zinc-400" />
          <span className="text-sm text-zinc-300">{typeLabel}</span>
          {isExpired && <Badge variant="danger" size="sm">Token Expired</Badge>}
        </div>

        {/* Name field */}
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={isPat ? "PAT Account" : "OAuth Account"}
          hint="Display name for this connection"
        />

        {/* Priority */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1.5">Priority</label>
          <input
            type="number"
            min={0}
            value={priority}
            onChange={(e) => setPriority(parseInt(e.target.value, 10) || 0)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
          <p className="text-xs text-zinc-500 mt-1">Lower = higher priority</p>
        </div>

        {/* Proxy Pool */}
        <div>
          <label className="block text-sm font-medium text-zinc-300 mb-1.5">Proxy Pool</label>
          <select
            value={proxyPoolId}
            onChange={(e) => setProxyPoolId(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3.5 py-2.5 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">None</option>
            {proxyPools.map((pool) => (
              <option key={pool.id} value={pool.id}>{pool.name}</option>
            ))}
          </select>
        </div>

        {/* Token info (read-only) */}
        <div className="bg-zinc-900/50 p-3 rounded-lg border border-zinc-700/40">
          <h4 className="text-xs font-medium text-zinc-400 mb-2">Token Info</h4>
          <div className="space-y-1.5">
            {connection.email && (
              <p className="text-xs text-zinc-500">
                <span className="text-zinc-400">Email:</span> {connection.email}
              </p>
            )}
            {expiresAt && (
              <p className="text-xs text-zinc-500">
                <span className="text-zinc-400">Expires:</span>{' '}
                {isExpired ? (
                  <span className="text-red-400">Expired</span>
                ) : (
                  new Date(expiresAt).toLocaleString()
                )}
              </p>
            )}
            {lastError && (
              <p className="text-xs text-red-400">
                <span className="text-zinc-400">Last Error:</span> {lastError}
              </p>
            )}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="rounded-lg border p-3 bg-red-950/30 border-red-700/40">
            <div className="flex items-center gap-2">
              <AlertCircle size={16} className="text-red-400 shrink-0" />
              <span className="text-sm text-red-300">{error}</span>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <><Loader2 size={14} className="animate-spin mr-1" /> Saving...</>
            ) : (
              'Save'
            )}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
