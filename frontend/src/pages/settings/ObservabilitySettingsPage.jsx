import { Activity } from 'lucide-react'
import Input from '../../components/ui/Input'
import Toggle from '../../components/ui/Toggle'
import { useSettings } from './SettingsContext'
import { Section, SettingRow, SettingsLoading } from './settingsUi'

export default function ObservabilitySettingsPage() {
  const { settings, savingFields, savedFields, updateField } = useSettings()
  if (!settings) return <SettingsLoading />

  return (
    <Section
      icon={Activity}
      title="Observability"
      description="Request logging and usage retention"
    >
      <SettingRow
        label="Enable observability"
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
        label="Max records"
        description="Maximum usage records to keep"
        saving={savingFields.observabilityMaxRecords}
        saved={savedFields.observabilityMaxRecords}
      >
        <Input
          type="number"
          min={100}
          max={100000}
          value={settings.observabilityMaxRecords}
          onChange={(e) =>
            updateField(
              'observabilityMaxRecords',
              parseInt(e.target.value) || 100,
            )
          }
          className="w-32 text-center"
        />
      </SettingRow>
      <SettingRow
        label="Batch size"
        description="Records per flush batch"
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
        label="Flush interval (ms)"
        description="How often data is flushed to storage"
        saving={savingFields.observabilityFlushIntervalMs}
        saved={savedFields.observabilityFlushIntervalMs}
      >
        <Input
          type="number"
          min={1000}
          max={60000}
          value={settings.observabilityFlushIntervalMs}
          onChange={(e) =>
            updateField(
              'observabilityFlushIntervalMs',
              parseInt(e.target.value) || 1000,
            )
          }
          className="w-32 text-center"
        />
      </SettingRow>
      <SettingRow
        label="Max JSON size (MB)"
        description="Maximum payload size for observability"
        saving={savingFields.observabilityMaxJsonSize}
        saved={savedFields.observabilityMaxJsonSize}
      >
        <Input
          type="number"
          min={1}
          max={100}
          value={settings.observabilityMaxJsonSize}
          onChange={(e) =>
            updateField(
              'observabilityMaxJsonSize',
              parseInt(e.target.value) || 1,
            )
          }
          className="w-24 text-center"
        />
      </SettingRow>
    </Section>
  )
}
