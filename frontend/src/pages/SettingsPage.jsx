import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Shield,
  GitBranch,
  Activity,
  Server,
  Zap,
  AlertTriangle,
  Check,
  Key,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import Badge from '../components/ui/Badge'
import { settingsApi } from '../api/settings'
import client from '../api/client'

// --- Theme hook ---

function useTheme() {
  const [theme, setThemeState] = useState(() => {
    if (typeof window === 'undefined') return 'system'
    return localStorage.getItem('9router-theme') || 'system'
  })

  const setTheme = (t) => {
    setThemeState(t)
    localStorage.setItem('9router-theme', t)
    const dark =
      t === 'dark' ||
      (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  }

  return { theme, setTheme }
}

// --- Section wrapper ---

function Section({ icon: Icon, title, description, badge, children }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-zinc-800">
            <Icon size={18} className="text-zinc-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-zinc-100">{title}</h3>
              {badge}
            </div>
            {description && (
              <p className="text-sm text-zinc-500 mt-0.5">{description}</p>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-5">{children}</div>
      </CardContent>
    </Card>
  )
}

// --- Setting row with inline save indicator ---

function SettingRow({ label, description, saving, saved, children }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-zinc-200">{label}</p>
        {description && (
          <p className="text-xs text-zinc-500 mt-0.5">{description}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {saving && <span className="text-xs text-zinc-500 animate-pulse">Saving...</span>}
        {saved && (
          <span className="text-xs text-emerald-400 flex items-center gap-1">
            <Check size={12} /> Saved
          </span>
        )}
        {children}
      </div>
    </div>
  )
}

// --- Select input ---

function SelectInput({ value, onChange, options, className = '' }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent hover:border-zinc-600 transition-colors ${className}`}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}

// --- JSON dict editor ---

function DictEditor({ value, onChange, placeholder = '{}', keyLabel = 'Key', valueLabel = 'Value' }) {
  const entries = Object.entries(value || {})
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')

  const addEntry = () => {
    if (!newKey.trim()) return
    onChange({ ...value, [newKey.trim()]: newValue })
    setNewKey('')
    setNewValue('')
  }

  const removeEntry = (key) => {
    const next = { ...value }
    delete next[key]
    onChange(next)
  }

  const updateEntry = (key, val) => {
    onChange({ ...value, [key]: val })
  }

  return (
    <div className="space-y-2 w-full max-w-md">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-xs text-zinc-400 font-mono min-w-[80px] truncate">{k}</span>
          <Input
            value={typeof v === 'string' ? v : JSON.stringify(v)}
            onChange={(e) => updateEntry(k, e.target.value)}
            className="flex-1 text-xs"
          />
          <button
            onClick={() => removeEntry(k)}
            className="text-zinc-500 hover:text-red-400 text-xs px-1"
          >
            ×
          </button>
        </div>
      ))}
      <div className="flex items-center gap-2">
        <Input
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          placeholder={keyLabel}
          className="flex-1 text-xs"
        />
        <Input
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          placeholder={valueLabel}
          className="flex-1 text-xs"
        />
        <button
          onClick={addEntry}
          className="text-xs text-primary-400 hover:text-primary-300 px-2 py-1 rounded bg-zinc-800"
        >
          +
        </button>
      </div>
    </div>
  )
}

// --- Auto-save hook ---

function useAutoSave(settings, setSettings, setSavingFields, setSavedFields) {
  const debounceRef = useRef({})

  const saveField = useCallback(async (key, value) => {
    if (debounceRef.current[key]) {
      clearTimeout(debounceRef.current[key])
    }

    const isText = typeof value === 'string'
    const delay = isText ? 500 : 0

    debounceRef.current[key] = setTimeout(async () => {
      setSavingFields(prev => ({ ...prev, [key]: true }))
      setSavedFields(prev => ({ ...prev, [key]: false }))
      try {
        const res = await settingsApi.update({ [key]: value })
        if (res?.data) {
          setSettings(res.data)
        }
        setSavedFields(prev => ({ ...prev, [key]: true }))
        setTimeout(() => setSavedFields(prev => ({ ...prev, [key]: false })), 2000)
      } catch (err) {
        console.error(`Failed to save ${key}:`, err)
      } finally {
        setSavingFields(prev => ({ ...prev, [key]: false }))
      }
    }, delay)
  }, [setSettings, setSavingFields, setSavedFields])

  return saveField
}

// --- Advanced Settings (collapsed) ---

function AdvancedSettings({ settings, updateField, savingFields, savedFields }) {
  const [open, setOpen] = useState(false)

  return (
    <Card>
      <button onClick={() => setOpen(v => !v)} className="w-full">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-zinc-800">
              <Zap size={18} className="text-zinc-400" />
            </div>
            <div className="flex-1 text-left">
              <h3 className="text-lg font-semibold text-zinc-100">Advanced Settings</h3>
              <p className="text-sm text-zinc-500">Cloud, Tunnel, Tailscale, Caveman, DNS</p>
            </div>
            <span className="text-zinc-500 text-sm">{open ? '▲' : '▼'}</span>
          </div>
        </CardHeader>
      </button>
      {open && (
        <CardContent className="space-y-6">
          {/* Cloud & Tunnel */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-zinc-300">Cloud & Tunnel</h4>
            <SettingRow label="Cloud Enabled" saving={savingFields.cloudEnabled} saved={savedFields.cloudEnabled}>
              <Toggle checked={settings.cloudEnabled} onChange={(v) => updateField('cloudEnabled', v)} />
            </SettingRow>
            <SettingRow label="Tunnel Enabled" saving={savingFields.tunnelEnabled} saved={savedFields.tunnelEnabled}>
              <Toggle checked={settings.tunnelEnabled} onChange={(v) => updateField('tunnelEnabled', v)} />
            </SettingRow>
            <SettingRow label="Tunnel Provider" saving={savingFields.tunnelProvider} saved={savedFields.tunnelProvider}>
              <SelectInput
                value={settings.tunnelProvider}
                onChange={(v) => updateField('tunnelProvider', v)}
                options={[
                  { value: 'cloudflare', label: 'Cloudflare' },
                  { value: 'ngrok', label: 'Ngrok' },
                ]}
                className="w-36"
              />
            </SettingRow>
            <SettingRow label="Tunnel URL" saving={savingFields.tunnelUrl} saved={savedFields.tunnelUrl}>
              <Input
                value={settings.tunnelUrl}
                onChange={(e) => updateField('tunnelUrl', e.target.value)}
                placeholder="https://tunnel.example.com"
                className="w-64"
              />
            </SettingRow>
            <SettingRow label="Dashboard via Tunnel" saving={savingFields.tunnelDashboardAccess} saved={savedFields.tunnelDashboardAccess}>
              <Toggle checked={settings.tunnelDashboardAccess} onChange={(v) => updateField('tunnelDashboardAccess', v)} />
            </SettingRow>
          </div>

          {/* Tailscale */}
          <div className="space-y-4 pt-4 border-t border-zinc-800">
            <h4 className="text-sm font-medium text-zinc-300">Tailscale</h4>
            <SettingRow label="Tailscale Enabled" saving={savingFields.tailscaleEnabled} saved={savedFields.tailscaleEnabled}>
              <Toggle checked={settings.tailscaleEnabled} onChange={(v) => updateField('tailscaleEnabled', v)} />
            </SettingRow>
            <SettingRow label="Tailscale URL" saving={savingFields.tailscaleUrl} saved={savedFields.tailscaleUrl}>
              <Input
                value={settings.tailscaleUrl}
                onChange={(e) => updateField('tailscaleUrl', e.target.value)}
                placeholder="https://machine.tailnet.ts.net"
                className="w-64"
              />
            </SettingRow>
          </div>

          {/* Caveman Mode */}
          <div className="space-y-4 pt-4 border-t border-zinc-800">
            <h4 className="text-sm font-medium text-zinc-300">Caveman Mode</h4>
            <SettingRow label="Caveman Enabled" saving={savingFields.cavemanEnabled} saved={savedFields.cavemanEnabled}>
              <Toggle checked={settings.cavemanEnabled} onChange={(v) => updateField('cavemanEnabled', v)} />
            </SettingRow>
            <SettingRow label="Caveman Level" saving={savingFields.cavemanLevel} saved={savedFields.cavemanLevel}>
              <SelectInput
                value={settings.cavemanLevel}
                onChange={(v) => updateField('cavemanLevel', v)}
                options={[
                  { value: 'full', label: 'Full' },
                  { value: 'minimal', label: 'Minimal' },
                  { value: 'off', label: 'Off' },
                ]}
                className="w-36"
              />
            </SettingRow>
          </div>

          {/* DNS Tool */}
          <div className="space-y-4 pt-4 border-t border-zinc-800">
            <h4 className="text-sm font-medium text-zinc-300">DNS Tool</h4>
            <SettingRow label="DNS Tool Enabled">
              <DictEditor
                value={settings.dnsToolEnabled}
                onChange={(v) => updateField('dnsToolEnabled', v)}
                keyLabel="Provider"
                valueLabel="true/false"
              />
            </SettingRow>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

// --- Main Settings Page ---

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingFields, setSavingFields] = useState({})
  const [savedFields, setSavedFields] = useState({})
  const { theme, setTheme } = useTheme()

  // Password change state
  const [passwords, setPasswords] = useState({ current: '', new: '', confirm: '' })
  const [passStatus, setPassStatus] = useState({ type: '', message: '' })
  const [passLoading, setPassLoading] = useState(false)

  // DB backup state
  const [dbLoading, setDbLoading] = useState(false)
  const [dbStatus, setDbStatus] = useState({ type: '', message: '' })

  // Shutdown modal
  const [shutdownOpen, setShutdownOpen] = useState(false)

  const saveField = useAutoSave(settings, setSettings, setSavingFields, setSavedFields)

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await settingsApi.get()
      setSettings(res.data)
    } catch (err) {
      console.error('Failed to fetch settings:', err)
      setError('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const updateField = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    saveField(key, value)
  }

  // --- Password change ---
  const handlePasswordChange = async (e) => {
    e.preventDefault()
    if (passwords.new !== passwords.confirm) {
      setPassStatus({ type: 'error', message: 'Passwords do not match' })
      return
    }
    setPassLoading(true)
    setPassStatus({ type: '', message: '' })
    try {
      const res = await settingsApi.update({
        currentPassword: passwords.current,
        newPassword: passwords.new,
      })
      if (res?.data) {
        setSettings(res.data)
        setPassStatus({ type: 'success', message: 'Password updated' })
        setPasswords({ current: '', new: '', confirm: '' })
      }
    } catch (err) {
      setPassStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to update password',
      })
    } finally {
      setPassLoading(false)
    }
  }

  // --- DB Export ---
  const handleExportDatabase = async () => {
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const res = await client.get('/settings/database')
      const content = JSON.stringify(res.data, null, 2)
      const blob = new Blob([content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      const stamp = new Date().toISOString().replace(/[.:]/g, '-')
      a.href = url
      a.download = `9router-backup-${stamp}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setDbStatus({ type: 'success', message: 'Backup downloaded' })
    } catch {
      setDbStatus({ type: 'error', message: 'Failed to export database' })
    } finally {
      setDbLoading(false)
    }
  }

  // --- DB Import ---
  const handleImportDatabase = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setDbLoading(true)
    setDbStatus({ type: '', message: '' })
    try {
      const raw = await file.text()
      const payload = JSON.parse(raw)
      const res = await client.post('/settings/database', payload)
      if (res.data?.success) {
        setDbStatus({ type: 'success', message: 'Database imported successfully' })
        fetchSettings()
      }
    } catch (err) {
      setDbStatus({
        type: 'error',
        message: err.response?.data?.detail || 'Failed to import database',
      })
    } finally {
      setDbLoading(false)
    }
  }

  // --- Shutdown ---
  const handleShutdown = async () => {
    try {
      await client.post('/version/shutdown')
    } catch {
      /* expected — server shutting down */
    }
  }

  // --- Logout ---
  const handleLogout = async () => {
    try {
      await client.post('/auth/logout')
      window.location.href = '/login'
    } catch {
      /* ignore */
    }
  }

  // --- Loading state ---
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent>
              <div className="animate-pulse space-y-4">
                <div className="h-5 w-40 rounded bg-zinc-800" />
                <div className="h-10 w-full rounded bg-zinc-800" />
                <div className="h-10 w-full rounded bg-zinc-800" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  // --- Error state ---
  if (error && !settings) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
        <AlertTriangle size={32} className="text-red-400 mb-4" />
        <p className="text-zinc-300 mb-4">{error}</p>
        <button onClick={fetchSettings} className="text-primary-400 hover:text-primary-300 underline">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Settings</h1>
          <p className="text-sm text-zinc-500 mt-1">Global configuration for 9Router</p>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {/* 1. Local Mode — Theme + DB Backup */}
      <Section icon={Server} title="Local Mode" description="Running on your machine">
        {/* Theme switcher */}
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-zinc-200">Theme</p>
          <div className="flex gap-1 p-1 rounded-lg bg-zinc-800">
            {['light', 'dark', 'system'].map((t) => (
              <button
                key={t}
                onClick={() => setTheme(t)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  theme === t
                    ? 'bg-zinc-600 text-white'
                    : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {t === 'light' ? '☀️' : t === 'dark' ? '🌙' : '💻'} {t}
              </button>
            ))}
          </div>
        </div>

        {/* DB backup/restore */}
        <div className="flex flex-col gap-2 pt-3 border-t border-zinc-800">
          <p className="text-xs text-zinc-500">Database backup & restore</p>
          <div className="flex gap-2">
            <button
              onClick={handleExportDatabase}
              disabled={dbLoading}
              className="px-3 py-2 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-colors disabled:opacity-50"
            >
              📥 Download Backup
            </button>
            <label className="px-3 py-2 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-colors cursor-pointer">
              📤 Import Backup
              <input type="file" accept=".json" className="hidden" onChange={handleImportDatabase} />
            </label>
          </div>
          {dbStatus.message && (
            <p className={`text-xs ${dbStatus.type === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
              {dbStatus.message}
            </p>
          )}
        </div>
      </Section>

      {/* 2. Security — Password only (Require Login + API Key are in /endpoint) */}
      <Section icon={Shield} title="Security" description="Change dashboard password">
        {/* Password change form */}
        <form onSubmit={handlePasswordChange} className="flex flex-col gap-3">
          <p className="text-xs text-zinc-500 font-medium">Change Password</p>
            {settings.hasPassword && (
              <Input
                type="password"
                placeholder="Current password"
                value={passwords.current}
                onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
              />
            )}
            <div className="grid grid-cols-2 gap-3">
              <Input
                type="password"
                placeholder="New password"
                value={passwords.new}
                onChange={(e) => setPasswords((p) => ({ ...p, new: e.target.value }))}
              />
              <Input
                type="password"
                placeholder="Confirm password"
                value={passwords.confirm}
                onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
              />
            </div>
            {passStatus.message && (
              <p className={`text-xs ${passStatus.type === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
                {passStatus.message}
              </p>
            )}
            <button
              type="submit"
              disabled={passLoading}
              className="self-start px-4 py-2 text-sm rounded-lg bg-zinc-700 hover:bg-zinc-600 transition-colors disabled:opacity-50"
            >
              {passLoading ? 'Saving...' : 'Update Password'}
            </button>
          </form>
      </Section>

      {/* 3. OIDC (only when authMode is not password) */}
      {settings.authMode !== 'password' && (
        <Section
          icon={Key}
          title="OIDC Configuration"
          description="OpenID Connect identity provider settings"
          badge={
            settings.oidcConfigured ? (
              <Badge variant="success" size="sm">Configured</Badge>
            ) : (
              <Badge variant="warning" size="sm">Not configured</Badge>
            )
          }
        >
          <SettingRow label="Auth Mode" saving={savingFields.authMode} saved={savedFields.authMode}>
            <SelectInput
              value={settings.authMode}
              onChange={(v) => updateField('authMode', v)}
              options={[
                { value: 'password', label: 'Password' },
                { value: 'oidc', label: 'OIDC' },
              ]}
              className="w-36"
            />
          </SettingRow>
          <SettingRow label="Issuer URL" saving={savingFields.oidcIssuerUrl} saved={savedFields.oidcIssuerUrl}>
            <Input
              value={settings.oidcIssuerUrl}
              onChange={(e) => updateField('oidcIssuerUrl', e.target.value)}
              placeholder="https://accounts.google.com"
              className="w-72"
            />
          </SettingRow>
          <SettingRow label="Client ID" saving={savingFields.oidcClientId} saved={savedFields.oidcClientId}>
            <Input
              value={settings.oidcClientId}
              onChange={(e) => updateField('oidcClientId', e.target.value)}
              placeholder="your-client-id"
              className="w-72"
            />
          </SettingRow>
          <SettingRow label="Client Secret" saving={savingFields.oidcClientSecret} saved={savedFields.oidcClientSecret}>
            <Input
              type="password"
              value=""
              onChange={(e) => updateField('oidcClientSecret', e.target.value)}
              placeholder="••••••••"
              className="w-72"
            />
          </SettingRow>
          <SettingRow label="Scopes" saving={savingFields.oidcScopes} saved={savedFields.oidcScopes}>
            <Input
              value={settings.oidcScopes}
              onChange={(e) => updateField('oidcScopes', e.target.value)}
              placeholder="openid profile email"
              className="w-72"
            />
          </SettingRow>
          <SettingRow label="Login Button Label" saving={savingFields.oidcLoginLabel} saved={savedFields.oidcLoginLabel}>
            <Input
              value={settings.oidcLoginLabel}
              onChange={(e) => updateField('oidcLoginLabel', e.target.value)}
              placeholder="Sign in with OIDC"
              className="w-72"
            />
          </SettingRow>
        </Section>
      )}

      {/* 4. Routing Strategy */}
      <Section icon={GitBranch} title="Routing Strategy" description="How requests are distributed across providers">
        <SettingRow
          label="Combo Strategy"
          description="Strategy for combo routing"
          saving={savingFields.comboStrategy}
          saved={savedFields.comboStrategy}
        >
          <SelectInput
            value={settings.comboStrategy}
            onChange={(v) => updateField('comboStrategy', v)}
            options={[
              { value: 'fallback', label: 'Fallback' },
              { value: 'round-robin', label: 'Round Robin' },
              { value: 'random', label: 'Random' },
            ]}
            className="w-40"
          />
        </SettingRow>
        <SettingRow
          label="Sticky Round Robin Limit"
          description="Consecutive requests before rotating"
          saving={savingFields.stickyRoundRobinLimit}
          saved={savedFields.stickyRoundRobinLimit}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.stickyRoundRobinLimit}
            onChange={(e) => updateField('stickyRoundRobinLimit', parseInt(e.target.value) || 1)}
            className="w-24 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Combo Sticky Limit"
          description="Sticky limit for combo-level round robin"
          saving={savingFields.comboStickyRoundRobinLimit}
          saved={savedFields.comboStickyRoundRobinLimit}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.comboStickyRoundRobinLimit}
            onChange={(e) => updateField('comboStickyRoundRobinLimit', parseInt(e.target.value) || 1)}
            className="w-24 text-center"
          />
        </SettingRow>
        <SettingRow label="Provider Strategies" description="Per-provider routing overrides">
          <DictEditor
            value={settings.providerStrategies}
            onChange={(v) => updateField('providerStrategies', v)}
            keyLabel="Provider"
            valueLabel="Strategy"
          />
        </SettingRow>
        <SettingRow label="Combo Strategies" description="Per-combo routing overrides">
          <DictEditor
            value={settings.comboStrategies}
            onChange={(v) => updateField('comboStrategies', v)}
            keyLabel="Combo"
            valueLabel="Strategy"
          />
        </SettingRow>
      </Section>

      {/* 5. Observability */}
      <Section icon={Activity} title="Observability" description="Request logging and usage tracking">
        <SettingRow
          label="Enable Observability"
          description="Track and log request usage data"
          saving={savingFields.enableObservability}
          saved={savedFields.enableObservability}
        >
          <Toggle checked={settings.enableObservability} onChange={(v) => updateField('enableObservability', v)} />
        </SettingRow>
        <SettingRow
          label="Max Records"
          description="Maximum usage records to keep"
          saving={savingFields.observabilityMaxRecords}
          saved={savedFields.observabilityMaxRecords}
        >
          <Input
            type="number"
            min={100}
            max={100000}
            value={settings.observabilityMaxRecords}
            onChange={(e) => updateField('observabilityMaxRecords', parseInt(e.target.value) || 100)}
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Batch Size"
          description="Records per flush batch"
          saving={savingFields.observabilityBatchSize}
          saved={savedFields.observabilityBatchSize}
        >
          <Input
            type="number"
            min={1}
            max={1000}
            value={settings.observabilityBatchSize}
            onChange={(e) => updateField('observabilityBatchSize', parseInt(e.target.value) || 1)}
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Flush Interval (ms)"
          description="How often data is flushed to storage"
          saving={savingFields.observabilityFlushIntervalMs}
          saved={savedFields.observabilityFlushIntervalMs}
        >
          <Input
            type="number"
            min={1000}
            max={60000}
            value={settings.observabilityFlushIntervalMs}
            onChange={(e) => updateField('observabilityFlushIntervalMs', parseInt(e.target.value) || 1000)}
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Max JSON Size (MB)"
          description="Maximum payload size for observability"
          saving={savingFields.observabilityMaxJsonSize}
          saved={savedFields.observabilityMaxJsonSize}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.observabilityMaxJsonSize}
            onChange={(e) => updateField('observabilityMaxJsonSize', parseInt(e.target.value) || 1)}
            className="w-24 text-center"
          />
        </SettingRow>
      </Section>

      {/* RTK (Real-Time Keys) */}
      <Section icon={AlertTriangle} title="RTK" description="Real-Time Keys subsystem"
        badge={<Badge variant="warning" size="sm">Experimental</Badge>}>
        <SettingRow
          label="RTK Enabled"
          description="Enable the RTK (Real-Time Keys) subsystem"
          saving={savingFields.rtkEnabled}
          saved={savedFields.rtkEnabled}
        >
          <Toggle checked={settings.rtkEnabled} onChange={(v) => updateField('rtkEnabled', v)} />
        </SettingRow>
      </Section>

      {/* 6. Advanced Settings (collapsed) */}
      <AdvancedSettings
        settings={settings}
        updateField={updateField}
        savingFields={savingFields}
        savedFields={savedFields}
      />

      {/* 7. Account Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => setShutdownOpen(true)}
          className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-red-800 text-red-400 hover:bg-red-950 transition-colors"
        >
          ⏻ Shutdown
        </button>
        <button
          onClick={handleLogout}
          className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-colors"
        >
          ↗ Logout
        </button>
      </div>

      {/* 8. App Info */}
      <div className="text-center text-xs text-zinc-600 py-4">
        <p>9Router</p>
        <p className="mt-1">Local Mode — All data stored on your machine</p>
      </div>

      {/* Shutdown confirmation modal */}
      {shutdownOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 rounded-xl p-6 max-w-sm w-full mx-4 border border-zinc-700">
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">Close Proxy</h3>
            <p className="text-sm text-zinc-400 mb-4">
              Are you sure you want to shut down the proxy server?
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShutdownOpen(false)}
                className="px-4 py-2 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={handleShutdown}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 text-white"
              >
                Shutdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
