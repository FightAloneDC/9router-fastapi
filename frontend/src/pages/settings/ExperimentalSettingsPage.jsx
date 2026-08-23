import { AlertTriangle, Zap } from 'lucide-react'
import Badge from '../../components/ui/Badge'
import Toggle from '../../components/ui/Toggle'
import { useSettings } from './SettingsContext'
import { Section, SettingRow, SelectInput, DictEditor, SettingsLoading } from './settingsUi'

export default function ExperimentalSettingsPage() {
  const { settings, savingFields, savedFields, updateField } = useSettings()
  if (!settings) return <SettingsLoading />

  return (
    <>
      <Section
        icon={Zap}
        title="RTK"
        description="Real-Time Keys subsystem"
        badge={<Badge variant="warning" size="sm">Experimental</Badge>}
      >
        <SettingRow
          label="RTK enabled"
          description="Enable the RTK subsystem"
          saving={savingFields.rtkEnabled}
          saved={savedFields.rtkEnabled}
        >
          <Toggle
            checked={settings.rtkEnabled}
            onChange={(v) => updateField('rtkEnabled', v)}
          />
        </SettingRow>
      </Section>

      <Section
        icon={AlertTriangle}
        title="Caveman mode"
        description="Legacy compatibility layer"
      >
        <SettingRow
          label="Caveman enabled"
          saving={savingFields.cavemanEnabled}
          saved={savedFields.cavemanEnabled}
        >
          <Toggle
            checked={settings.cavemanEnabled}
            onChange={(v) => updateField('cavemanEnabled', v)}
          />
        </SettingRow>
        <SettingRow
          label="Caveman level"
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

      <Section icon={Zap} title="DNS tool" description="Per-provider DNS overrides">
        <SettingRow label="DNS tool enabled">
          <DictEditor
            value={settings.dnsToolEnabled}
            onChange={(v) => updateField('dnsToolEnabled', v)}
            keyLabel="Provider"
            valueLabel="true/false"
          />
        </SettingRow>
      </Section>
    </>
  )
}
