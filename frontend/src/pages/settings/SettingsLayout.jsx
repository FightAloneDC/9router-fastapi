import { Outlet } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { SettingsProvider, useSettings } from './SettingsContext'

function SettingsLayoutBody() {
  const { error, settings, fetchSettings } = useSettings()

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {error && !settings && (
        <div
          className="flex items-center gap-3 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-sm"
        >
          <AlertTriangle size={16} className="text-red-400 shrink-0" />
          <p className="text-zinc-300 flex-1">{error}</p>
          <button
            onClick={fetchSettings}
            className="text-primary-400 hover:text-primary-300 text-xs font-medium"
          >
            Retry
          </button>
        </div>
      )}
      <Outlet />
    </div>
  )
}

export default function SettingsLayout() {
  return (
    <SettingsProvider>
      <SettingsLayoutBody />
    </SettingsProvider>
  )
}
