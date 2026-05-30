import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { authApi } from '../api/auth'
import { Lock, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [checkingStatus, setCheckingStatus] = useState(true)
  const [statusData, setStatusData] = useState(null)
  const login = useAuthStore((state) => state.login)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const checkAuth = useAuthStore((state) => state.checkAuth)
  const navigate = useNavigate()

  useEffect(() => {
    const init = async () => {
      // Check if already logged in
      if (isAuthenticated) {
        const valid = await checkAuth()
        if (valid) {
          navigate('/', { replace: true })
          return
        }
      }
      // Fetch auth status
      try {
        const res = await authApi.status()
        setStatusData(res.data)
        // If login not required, skip
        if (!res.data.requireLogin) {
          navigate('/', { replace: true })
          return
        }
      } catch {
        // Default to requiring login
        setStatusData({ requireLogin: true, hasPassword: false })
      }
      setCheckingStatus(false)
    }
    init()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await login(password)
    setLoading(false)

    if (result.success) {
      navigate('/', { replace: true })
    } else {
      setError(result.error)
    }
  }

  // Loading spinner while checking auth status
  if (checkingStatus) {
    return (
      <div className="w-full max-w-md">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl p-8">
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 size={32} className="text-primary-400 animate-spin" />
            <p className="mt-4 text-zinc-400 text-sm">Checking authentication...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-md">
      {/* 9Router Branding */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 mb-4 shadow-lg shadow-primary-500/25">
          <Lock size={28} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white tracking-tight">9Router</h1>
        <p className="mt-2 text-zinc-400 text-sm">Network Management Dashboard</p>
      </div>

      {/* Login Card */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden">
        <div className="p-6 pb-0">
          <h2 className="text-lg font-semibold text-zinc-100">Sign In</h2>
          <p className="mt-1 text-sm text-zinc-500">Enter your password to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoFocus
              className="w-full px-3 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500 transition-colors"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !password}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary-600 hover:bg-primary-700 disabled:bg-zinc-700 disabled:text-zinc-500 text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </button>

          {/* Default password hint */}
          {!statusData?.hasPassword && (
            <div className="rounded-lg bg-primary-500/10 border border-primary-500/20 px-4 py-3">
              <p className="text-sm text-primary-300">
                <span className="font-medium">Default password is 123456</span>
              </p>
              <p className="text-xs text-primary-400/70 mt-1">
                This will create the admin account on first login
              </p>
            </div>
          )}
        </form>
      </div>

      <p className="text-center text-zinc-600 text-xs mt-6">
        9Router &mdash; Network Management Dashboard
      </p>
    </div>
  )
}
