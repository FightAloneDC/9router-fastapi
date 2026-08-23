import { useState } from 'react'
import { Shield, Key } from 'lucide-react'
import Input from '../../components/ui/Input'
import Badge from '../../components/ui/Badge'
import { settingsApi } from '../../api/settings'
import { useSettings } from './SettingsContext'
import { Section, SettingRow, SelectInput, SettingsLoading } from './settingsUi'

export default function SecuritySettingsPage() {
  const {
    settings,
    savingFields,
    savedFields,
    updateField,
    fetchSettings,
  } = useSettings()

  const [passwords, setPasswords] = useState({ current: '', new: '', confirm: '' })
  const [passStatus, setPassStatus] = useState({ type: '', message: '' })
  const [passLoading, setPassLoading] = useState(false)

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
        setPassStatus({ type: 'success', message: 'Password updated' })
        setPasswords({ current: '', new: '', confirm: '' })
        fetchSettings()
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

  if (!settings) return <SettingsLoading />

  return (
    <>
      <Section
        icon={Shield}
        title="Dashboard password"
        description="Password for signing into this UI"
      >
        <form onSubmit={handlePasswordChange} className="flex flex-col gap-3">
          {settings.hasPassword && (
            <Input
              type="password"
              placeholder="Current password"
              value={passwords.current}
              onChange={(e) =>
                setPasswords((p) => ({ ...p, current: e.target.value }))
              }
            />
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              type="password"
              placeholder="New password"
              value={passwords.new}
              onChange={(e) =>
                setPasswords((p) => ({ ...p, new: e.target.value }))
              }
            />
            <Input
              type="password"
              placeholder="Confirm password"
              value={passwords.confirm}
              onChange={(e) =>
                setPasswords((p) => ({ ...p, confirm: e.target.value }))
              }
            />
          </div>
          {passStatus.message && (
            <p
              className={`text-xs ${
                passStatus.type === 'error' ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {passStatus.message}
            </p>
          )}
          <button
            type="submit"
            disabled={passLoading}
            className="self-start px-4 py-2 text-sm rounded-lg bg-zinc-700 hover:bg-zinc-600 transition-colors disabled:opacity-50"
          >
            {passLoading ? 'Saving...' : 'Update password'}
          </button>
        </form>
      </Section>

      <Section
        icon={Key}
        title="Authentication mode"
        description="Password login or OpenID Connect"
        badge={
          settings.authMode === 'oidc' && settings.oidcConfigured ? (
            <Badge variant="success" size="sm">OIDC ready</Badge>
          ) : null
        }
      >
        <SettingRow
          label="Auth mode"
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

        {settings.authMode !== 'password' && (
          <>
            <SettingRow
              label="Issuer URL"
              saving={savingFields.oidcIssuerUrl}
              saved={savedFields.oidcIssuerUrl}
            >
              <Input
                value={settings.oidcIssuerUrl}
                onChange={(e) => updateField('oidcIssuerUrl', e.target.value)}
                placeholder="https://accounts.google.com"
                className="w-full max-w-md"
              />
            </SettingRow>
            <SettingRow
              label="Client ID"
              saving={savingFields.oidcClientId}
              saved={savedFields.oidcClientId}
            >
              <Input
                value={settings.oidcClientId}
                onChange={(e) => updateField('oidcClientId', e.target.value)}
                placeholder="your-client-id"
                className="w-full max-w-md"
              />
            </SettingRow>
            <SettingRow
              label="Client secret"
              saving={savingFields.oidcClientSecret}
              saved={savedFields.oidcClientSecret}
            >
              <Input
                type="password"
                value=""
                onChange={(e) => updateField('oidcClientSecret', e.target.value)}
                placeholder="••••••••"
                className="w-full max-w-md"
              />
            </SettingRow>
            <SettingRow
              label="Scopes"
              saving={savingFields.oidcScopes}
              saved={savedFields.oidcScopes}
            >
              <Input
                value={settings.oidcScopes}
                onChange={(e) => updateField('oidcScopes', e.target.value)}
                placeholder="openid profile email"
                className="w-full max-w-md"
              />
            </SettingRow>
            <SettingRow
              label="Login button label"
              saving={savingFields.oidcLoginLabel}
              saved={savedFields.oidcLoginLabel}
            >
              <Input
                value={settings.oidcLoginLabel}
                onChange={(e) => updateField('oidcLoginLabel', e.target.value)}
                placeholder="Sign in with OIDC"
                className="w-full max-w-md"
              />
            </SettingRow>
          </>
        )}
      </Section>
    </>
  )
}
