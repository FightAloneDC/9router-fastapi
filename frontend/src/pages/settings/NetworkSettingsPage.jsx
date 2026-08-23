import { Globe } from 'lucide-react'
import Input from '../../components/ui/Input'
import Toggle from '../../components/ui/Toggle'
import { useSettings } from './SettingsContext'
import { Section, SettingRow, SelectInput, SettingsLoading } from './settingsUi'

export default function NetworkSettingsPage() {
  const { settings, savingFields, savedFields, updateField } = useSettings()
  if (!settings) return <SettingsLoading />

  return (
    <>
      <Section
        icon={Globe}
        title="Cloud & tunnel"
        description="Expose this instance through a tunnel provider"
      >
        <SettingRow
          label="Cloud enabled"
          saving={savingFields.cloudEnabled}
          saved={savedFields.cloudEnabled}
        >
          <Toggle
            checked={settings.cloudEnabled}
            onChange={(v) => updateField('cloudEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Tunnel enabled"
          saving={savingFields.tunnelEnabled}
          saved={savedFields.tunnelEnabled}
        >
          <Toggle
            checked={settings.tunnelEnabled}
            onChange={(v) => updateField('tunnelEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Tunnel provider"
          saving={savingFields.tunnelProvider}
          saved={savedFields.tunnelProvider}
        >
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
        <SettingRow
          label="Tunnel URL"
          saving={savingFields.tunnelUrl}
          saved={savedFields.tunnelUrl}
        >
          <Input
            value={settings.tunnelUrl}
            onChange={(e) => updateField('tunnelUrl', e.target.value)}
            placeholder="https://tunnel.example.com"
            className="w-full max-w-md"
          />
        </SettingRow>
        <SettingRow
          label="Dashboard via tunnel"
          saving={savingFields.tunnelDashboardAccess}
          saved={savedFields.tunnelDashboardAccess}
        >
          <Toggle
            checked={settings.tunnelDashboardAccess}
            onChange={(v) => updateField('tunnelDashboardAccess', v)}
          />
        </SettingRow>
      </Section>

      <Section
        icon={Globe}
        title="Tailscale"
        description="Private tailnet access"
      >
        <SettingRow
          label="Tailscale enabled"
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
          saving={savingFields.tailscaleUrl}
          saved={savedFields.tailscaleUrl}
        >
          <Input
            value={settings.tailscaleUrl}
            onChange={(e) => updateField('tailscaleUrl', e.target.value)}
            placeholder="https://machine.tailnet.ts.net"
            className="w-full max-w-md"
          />
        </SettingRow>
      </Section>
    </>
  )
}
