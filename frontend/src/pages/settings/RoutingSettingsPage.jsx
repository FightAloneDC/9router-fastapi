import { GitBranch } from 'lucide-react'
import Input from '../../components/ui/Input'
import { useSettings } from './SettingsContext'
import {
  Section,
  SettingRow,
  SelectInput,
  DictEditor,
  SettingsLoading,
} from './settingsUi'

export default function RoutingSettingsPage() {
  const { settings, savingFields, savedFields, updateField } = useSettings()
  if (!settings) return <SettingsLoading />

  return (
    <Section
      icon={GitBranch}
      title="Routing strategy"
      description="How combos and providers pick the next connection"
    >
      <SettingRow
        label="Combo strategy"
        description="Default strategy for combo routing"
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
        label="Sticky round robin limit"
        description="Consecutive requests before rotating"
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
        label="Combo sticky limit"
        description="Sticky limit at combo level"
        saving={savingFields.comboStickyRoundRobinLimit}
        saved={savedFields.comboStickyRoundRobinLimit}
      >
        <Input
          type="number"
          min={1}
          max={100}
          value={settings.comboStickyRoundRobinLimit}
          onChange={(e) =>
            updateField(
              'comboStickyRoundRobinLimit',
              parseInt(e.target.value) || 1,
            )
          }
          className="w-24 text-center"
        />
      </SettingRow>
      <SettingRow
        label="Provider strategies"
        description="Per-provider routing overrides"
      >
        <DictEditor
          value={settings.providerStrategies}
          onChange={(v) => updateField('providerStrategies', v)}
          keyLabel="Provider"
          valueLabel="Strategy"
        />
      </SettingRow>
      <SettingRow
        label="Combo strategies"
        description="Per-combo routing overrides"
      >
        <DictEditor
          value={settings.comboStrategies}
          onChange={(v) => updateField('comboStrategies', v)}
          keyLabel="Combo"
          valueLabel="Strategy"
        />
      </SettingRow>
    </Section>
  )
}
