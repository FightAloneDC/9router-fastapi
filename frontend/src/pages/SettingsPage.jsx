import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Shield,
  Cloud,
  Network,
  GitBranch,
  Activity,
  Crosshair,
  AlertTriangle,
  Check,
  Key,
  Globe,
  Server,
  Zap,
  Lock,
} from 'lucide-react'
import Card, { CardContent, CardHeader } from '../components/ui/Card'
import Input from '../components/ui/Input'
import Toggle from '../components/ui/Toggle'
import Badge from '../components/ui/Badge'
import { settingsApi } from '../api/settings'

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

// --- JSON dict editor for providerStrategies, comboStrategies, dnsToolEnabled ---

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
    // Clear previous debounce for this field
    if (debounceRef.current[key]) {
      clearTimeout(debounceRef.current[key])
    }

    // For text inputs, debounce 500ms. For toggles/selects, save immediately.
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

// --- Main Settings Page ---

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [savingFields, setSavingFields] = useState({})
  const [savedFields, setSavedFields] = useState({})

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

  if (loading) {
    return (
      <div className="space-y-6">
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Settings</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Global configuration for 9Router
          </p>
        </div>
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
      </div>

      {/* Authentication */}
      <Section
        icon={Shield}
        title="Authentication"
        description="Control login and API key requirements"
      >
        <SettingRow
          label="Require Login"
          description="Users must authenticate before accessing the dashboard"
          saving={savingFields.requireLogin}
          saved={savedFields.requireLogin}
        >
          <Toggle
            checked={settings.requireLogin}
            onChange={(v) => updateField('requireLogin', v)}
          />
        </SettingRow>
        <SettingRow
          label="Require API Key"
          description="API requests must include a valid API key"
          saving={savingFields.requireApiKey}
          saved={savedFields.requireApiKey}
        >
          <Toggle
            checked={settings.requireApiKey}
            onChange={(v) => updateField('requireApiKey', v)}
          />
        </SettingRow>
        <SettingRow
          label="Auth Mode"
          description="Authentication method for user login"
          saving={savingFields.authMode}
          saved={savedFields.authMode}
        >
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
      </Section>

      {/* OIDC — only show when authMode is oidc */}
      {settings.authMode === 'oidc' && (
        <Section
          icon={Key}
          title="OIDC Configuration"
          description="OpenID Connect identity provider settings"
          badge={settings.oidcConfigured ? <Badge variant="success" size="sm">Configured</Badge> : <Badge variant="warning" size="sm">Not configured</Badge>}
        >
          <SettingRow
            label="Issuer URL"
            description="OIDC provider issuer URL"
            saving={savingFields.oidcIssuerUrl}
            saved={savedFields.oidcIssuerUrl}
          >
            <Input
              value={settings.oidcIssuerUrl}
              onChange={(e) => updateField('oidcIssuerUrl', e.target.value)}
              placeholder="https://accounts.google.com"
              className="w-72"
            />
          </SettingRow>
          <SettingRow
            label="Client ID"
            description="OIDC application client ID"
            saving={savingFields.oidcClientId}
            saved={savedFields.oidcClientId}
          >
            <Input
              value={settings.oidcClientId}
              onChange={(e) => updateField('oidcClientId', e.target.value)}
              placeholder="your-client-id"
              className="w-72"
            />
          </SettingRow>
          <SettingRow
            label="Client Secret"
            description="OIDC application client secret"
            saving={savingFields.oidcClientSecret}
            saved={savedFields.oidcClientSecret}
          >
            <Input
              type="password"
              value=""
              onChange={(e) => updateField('oidcClientSecret', e.target.value)}
              placeholder="••••••••"
              className="w-72"
            />
          </SettingRow>
          <SettingRow
            label="Scopes"
            description="OIDC scopes to request"
            saving={savingFields.oidcScopes}
            saved={savedFields.oidcScopes}
          >
            <Input
              value={settings.oidcScopes}
              onChange={(e) => updateField('oidcScopes', e.target.value)}
              placeholder="openid profile email"
              className="w-72"
            />
          </SettingRow>
          <SettingRow
            label="Login Button Label"
            description="Text shown on the OIDC login button"
            saving={savingFields.oidcLoginLabel}
            saved={savedFields.oidcLoginLabel}
          >
            <Input
              value={settings.oidcLoginLabel}
              onChange={(e) => updateField('oidcLoginLabel', e.target.value)}
              placeholder="Sign in with OIDC"
              className="w-72"
            />
          </SettingRow>
        </Section>
      )}

      {/* Cloud & Tunnel */}
      <Section
        icon={Cloud}
        title="Cloud & Tunnel"
        description="Configure cloud features and tunnel connectivity"
        badge={
          settings.cloudEnabled ? (
            <Badge variant="success" size="sm">Enabled</Badge>
          ) : null
        }
      >
        <SettingRow
          label="Cloud Enabled"
          description="Enable cloud-based features and sync"
          saving={savingFields.cloudEnabled}
          saved={savedFields.cloudEnabled}
        >
          <Toggle
            checked={settings.cloudEnabled}
            onChange={(v) => updateField('cloudEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Tunnel Enabled"
          description="Expose local services via a tunnel"
          saving={savingFields.tunnelEnabled}
          saved={savedFields.tunnelEnabled}
        >
          <Toggle
            checked={settings.tunnelEnabled}
            onChange={(v) => updateField('tunnelEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Tunnel Provider"
          description="Service used to create the tunnel"
          saving={savingFields.tunnelProvider}
          saved={savedFields.tunnelProvider}
        >
          <SelectInput
            value={settings.tunnelProvider}
            onChange={(v) => updateField('tunnelProvider', v)}
            options={[
              { value: 'cloudflare', label: 'Cloudflare' },
              { value: 'ngrok', label: 'Ngrok' },
              { value: 'tailscale', label: 'Tailscale' },
            ]}
            className="w-36"
          />
        </SettingRow>
        <SettingRow
          label="Tunnel URL"
          description="Public URL of the tunnel endpoint"
          saving={savingFields.tunnelUrl}
          saved={savedFields.tunnelUrl}
        >
          <Input
            value={settings.tunnelUrl}
            onChange={(e) => updateField('tunnelUrl', e.target.value)}
            placeholder="https://tunnel.example.com"
            className="w-72"
          />
        </SettingRow>
        <SettingRow
          label="Tunnel Dashboard Access"
          description="Allow dashboard access through the tunnel"
          saving={savingFields.tunnelDashboardAccess}
          saved={savedFields.tunnelDashboardAccess}
        >
          <Toggle
            checked={settings.tunnelDashboardAccess}
            onChange={(v) => updateField('tunnelDashboardAccess', v)}
          />
        </SettingRow>
      </Section>

      {/* Tailscale */}
      <Section
        icon={Globe}
        title="Tailscale"
        description="Tailscale VPN connectivity"
        badge={
          settings.tailscaleEnabled ? (
            <Badge variant="success" size="sm">Enabled</Badge>
          ) : null
        }
      >
        <SettingRow
          label="Tailscale Enabled"
          description="Enable Tailscale VPN access"
          saving={savingFields.tailscaleEnabled}
          saved={savedFields.tailscaleEnabled}
        >
          <Toggle
            checked={settings.tailscaleEnabled}
            onChange={(v) => updateField('tailscaleEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Tailscale URL"
          description="Tailscale serve URL"
          saving={savingFields.tailscaleUrl}
          saved={savedFields.tailscaleUrl}
        >
          <Input
            value={settings.tailscaleUrl}
            onChange={(e) => updateField('tailscaleUrl', e.target.value)}
            placeholder="https://your-machine.tailnet.ts.net"
            className="w-72"
          />
        </SettingRow>
      </Section>

      {/* Outbound Proxy */}
      <Section
        icon={Network}
        title="Outbound Proxy"
        description="Route outbound requests through a proxy"
      >
        <SettingRow
          label="Outbound Proxy Enabled"
          description="Use a proxy for all outbound HTTP requests"
          saving={savingFields.outboundProxyEnabled}
          saved={savedFields.outboundProxyEnabled}
        >
          <Toggle
            checked={settings.outboundProxyEnabled}
            onChange={(v) => updateField('outboundProxyEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Proxy URL"
          description="Proxy server URL (e.g. http://proxy:8080)"
          saving={savingFields.outboundProxyUrl}
          saved={savedFields.outboundProxyUrl}
        >
          <Input
            value={settings.outboundProxyUrl}
            onChange={(e) => updateField('outboundProxyUrl', e.target.value)}
            placeholder="http://proxy:8080"
            className="w-72"
          />
        </SettingRow>
        <SettingRow
          label="No Proxy Hosts"
          description="Comma-separated hosts that bypass the proxy"
          saving={savingFields.outboundNoProxy}
          saved={savedFields.outboundNoProxy}
        >
          <Input
            value={settings.outboundNoProxy}
            onChange={(e) => updateField('outboundNoProxy', e.target.value)}
            placeholder="localhost,127.0.0.1,.internal"
            className="w-72"
          />
        </SettingRow>
      </Section>

      {/* Routing Strategy */}
      <Section
        icon={GitBranch}
        title="Routing Strategy"
        description="How requests are distributed across providers"
      >
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
          description="Number of consecutive requests before rotating"
          saving={savingFields.stickyRoundRobinLimit}
          saved={savedFields.stickyRoundRobinLimit}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.stickyRoundRobinLimit}
            onChange={(e) =>
              updateField('stickyRoundRobinLimit', parseInt(e.target.value) || 1)
            }
            className="w-24 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Combo Sticky Round Robin Limit"
          description="Sticky limit for combo-level round robin"
          saving={savingFields.comboStickyRoundRobinLimit}
          saved={savedFields.comboStickyRoundRobinLimit}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.comboStickyRoundRobinLimit}
            onChange={(e) =>
              updateField('comboStickyRoundRobinLimit', parseInt(e.target.value) || 1)
            }
            className="w-24 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Provider Strategies"
          description="Per-provider routing strategy overrides"
        >
          <DictEditor
            value={settings.providerStrategies}
            onChange={(v) => updateField('providerStrategies', v)}
            keyLabel="Provider"
            valueLabel="Strategy"
          />
        </SettingRow>
        <SettingRow
          label="Combo Strategies"
          description="Per-combo routing strategy overrides"
        >
          <DictEditor
            value={settings.comboStrategies}
            onChange={(v) => updateField('comboStrategies', v)}
            keyLabel="Combo"
            valueLabel="Strategy"
          />
        </SettingRow>
      </Section>

      {/* Observability */}
      <Section
        icon={Activity}
        title="Observability"
        description="Request logging and usage tracking"
      >
        <SettingRow
          label="Enable Observability"
          description="Track and log request usage data"
          saving={savingFields.enableObservability}
          saved={savedFields.enableObservability}
        >
          <Toggle
            checked={settings.enableObservability}
            onChange={(v) => updateField('enableObservability', v)}
          />
        </SettingRow>
        <SettingRow
          label="Max Records"
          description="Maximum number of usage records to keep"
          saving={savingFields.observabilityMaxRecords}
          saved={savedFields.observabilityMaxRecords}
        >
          <Input
            type="number"
            min={100}
            max={100000}
            value={settings.observabilityMaxRecords}
            onChange={(e) =>
              updateField('observabilityMaxRecords', parseInt(e.target.value) || 100)
            }
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Batch Size"
          description="Number of records per flush batch"
          saving={savingFields.observabilityBatchSize}
          saved={savedFields.observabilityBatchSize}
        >
          <Input
            type="number"
            min={1}
            max={1000}
            value={settings.observabilityBatchSize}
            onChange={(e) =>
              updateField('observabilityBatchSize', parseInt(e.target.value) || 1)
            }
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Flush Interval (ms)"
          description="How often usage data is flushed to storage"
          saving={savingFields.observabilityFlushIntervalMs}
          saved={savedFields.observabilityFlushIntervalMs}
        >
          <Input
            type="number"
            min={1000}
            max={60000}
            value={settings.observabilityFlushIntervalMs}
            onChange={(e) =>
              updateField('observabilityFlushIntervalMs', parseInt(e.target.value) || 1000)
            }
            className="w-32 text-center"
          />
        </SettingRow>
        <SettingRow
          label="Max JSON Size (MB)"
          description="Maximum JSON payload size for observability"
          saving={savingFields.observabilityMaxJsonSize}
          saved={savedFields.observabilityMaxJsonSize}
        >
          <Input
            type="number"
            min={1}
            max={100}
            value={settings.observabilityMaxJsonSize}
            onChange={(e) =>
              updateField('observabilityMaxJsonSize', parseInt(e.target.value) || 1)
            }
            className="w-24 text-center"
          />
        </SettingRow>
      </Section>

      {/* MITM */}
      <Section
        icon={Crosshair}
        title="MITM"
        description="Man-in-the-middle proxy configuration"
      >
        <SettingRow
          label="MITM Router Base URL"
          description="Base URL of the MITM proxy service"
          saving={savingFields.mitmRouterBaseUrl}
          saved={savedFields.mitmRouterBaseUrl}
        >
          <Input
            value={settings.mitmRouterBaseUrl}
            onChange={(e) => updateField('mitmRouterBaseUrl', e.target.value)}
            placeholder="http://localhost:20128"
            className="w-72"
          />
        </SettingRow>
      </Section>

      {/* Caveman Mode */}
      <Section
        icon={Zap}
        title="Caveman Mode"
        description="Minimalist response mode for reduced overhead"
        badge={
          settings.cavemanEnabled ? (
            <Badge variant="success" size="sm">Enabled</Badge>
          ) : null
        }
      >
        <SettingRow
          label="Caveman Enabled"
          description="Enable caveman response mode"
          saving={savingFields.cavemanEnabled}
          saved={savedFields.cavemanEnabled}
        >
          <Toggle
            checked={settings.cavemanEnabled}
            onChange={(v) => updateField('cavemanEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Caveman Level"
          description="Level of caveman mode aggressiveness"
          saving={savingFields.cavemanLevel}
          saved={savedFields.cavemanLevel}
        >
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
      </Section>

      {/* DNS Tool */}
      <Section
        icon={Server}
        title="DNS Tool"
        description="Per-provider DNS tool configuration"
      >
        <SettingRow
          label="DNS Tool Enabled"
          description="Enable/disable DNS tool per provider"
        >
          <DictEditor
            value={settings.dnsToolEnabled}
            onChange={(v) => updateField('dnsToolEnabled', v)}
            keyLabel="Provider"
            valueLabel="true/false"
          />
        </SettingRow>
      </Section>

      {/* Danger Zone */}
      <Section
        icon={AlertTriangle}
        title="Danger Zone"
        description="Advanced settings — modify with caution"
        badge={<Badge variant="danger" size="sm">Caution</Badge>}
      >
        <SettingRow
          label="RTK Enabled"
          description="Enable the RTK (Real-Time Keys) subsystem"
          saving={savingFields.rtkEnabled}
          saved={savedFields.rtkEnabled}
        >
          <Toggle
            checked={settings.rtkEnabled}
            onChange={(v) => updateField('rtkEnabled', v)}
          />
        </SettingRow>
      </Section>
    </div>
  )
}
