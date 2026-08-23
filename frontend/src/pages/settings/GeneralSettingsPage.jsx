import { useState } from 'react'
import { Monitor } from 'lucide-react'
import client from '../../api/client'
import { Section, useTheme } from './settingsUi'

export default function GeneralSettingsPage() {
  const { theme, setTheme } = useTheme()
  const [shutdownOpen, setShutdownOpen] = useState(false)

  const handleShutdown = async () => {
    try {
      await client.post('/version/shutdown')
    } catch {
      /* expected */
    }
  }

  const handleLogout = async () => {
    try {
      await client.post('/auth/logout')
      window.location.href = '/login'
    } catch {
      /* ignore */
    }
  }

  return (
    <>
      <Section
        icon={Monitor}
        title="Appearance"
        description="How the dashboard looks on your machine"
      >
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-200">Theme</p>
            <p className="text-xs text-zinc-500 mt-0.5">
              Light, dark, or follow system preference
            </p>
          </div>
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
      </Section>

      <Section
        icon={Monitor}
        title="System"
        description="Process control and session"
      >
        <div className="flex gap-2">
          <button
            onClick={() => setShutdownOpen(true)}
            className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-red-800 text-red-400 hover:bg-red-950 transition-colors"
          >
            Shutdown server
          </button>
          <button
            onClick={handleLogout}
            className="flex-1 px-4 py-2.5 text-sm rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-colors"
          >
            Logout
          </button>
        </div>
      </Section>

      <div className="text-center text-xs text-zinc-600 py-2">
        <p>9Router — local mode, data stored on this machine</p>
      </div>

      {shutdownOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-zinc-900 rounded-xl p-6 max-w-sm w-full mx-4 border border-zinc-700">
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">
              Shutdown server?
            </h3>
            <p className="text-sm text-zinc-400 mb-4">
              The proxy process will stop. Production containers are unaffected
              if you run dev on the host separately.
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
    </>
  )
}
