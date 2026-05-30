import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Shield,
  Building2,
  Upload,
  Globe,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  ExternalLink,
  RefreshCw,
} from 'lucide-react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import Input from './ui/Input'

export default function KiroAuthModal({ isOpen, onMethodSelect, onClose }) {
  const [selectedMethod, setSelectedMethod] = useState(null)
  const [idcStartUrl, setIdcStartUrl] = useState('')
  const [idcRegion, setIdcRegion] = useState('us-east-1')
  const [refreshToken, setRefreshToken] = useState('')
  const [error, setError] = useState(null)
  const [importing, setImporting] = useState(false)
  const [autoDetecting, setAutoDetecting] = useState(false)
  const [autoDetected, setAutoDetected] = useState(false)

  // Social login sub-modal state
  const [socialOpen, setSocialOpen] = useState(false)
  const [socialProvider, setSocialProvider] = useState(null)
  const [socialStep, setSocialStep] = useState('loading') // loading | input | success | error
  const [socialAuthUrl, setSocialAuthUrl] = useState('')
  const [socialAuthData, setSocialAuthData] = useState(null)
  const [socialCallbackUrl, setSocialCallbackUrl] = useState('')
  const [socialError, setSocialError] = useState(null)
  const [copiedField, setCopiedField] = useState(null)

  const handleCopy = useCallback(async (text, field) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch {
      // clipboard not available
    }
  }, [])

  // Auto-detect token when import method is selected
  useEffect(() => {
    if (selectedMethod !== 'import' || !isOpen) return

    const autoDetect = async () => {
      setAutoDetecting(true)
      setError(null)
      setAutoDetected(false)

      try {
        const res = await fetch('/api/oauth/kiro/auto-import')
        const data = await res.json()

        if (data.found) {
          setRefreshToken(data.refreshToken)
          setAutoDetected(true)
        } else {
          setError(data.error || 'Could not auto-detect token')
        }
      } catch {
        setError('Failed to auto-detect token')
      } finally {
        setAutoDetecting(false)
      }
    }

    autoDetect()
  }, [selectedMethod, isOpen])

  // Initialize social auth flow
  useEffect(() => {
    if (!socialOpen || !socialProvider) return

    const initAuth = async () => {
      try {
        setSocialError(null)
        setSocialStep('loading')

        const res = await fetch(`/api/oauth/kiro/social-authorize?provider=${socialProvider}`)
        const data = await res.json()

        if (!res.ok) {
          throw new Error(data.error)
        }

        setSocialAuthData(data)
        setSocialAuthUrl(data.authUrl)
        setSocialStep('input')

        // Auto-open browser
        window.open(data.authUrl, '_blank')
      } catch (err) {
        setSocialError(err.message)
        setSocialStep('error')
      }
    }

    initAuth()
  }, [socialOpen, socialProvider])

  const handleMethodSelect = (method) => {
    setSelectedMethod(method)
    setError(null)
  }

  const handleBack = () => {
    setSelectedMethod(null)
    setError(null)
  }

  const handleImportToken = async () => {
    if (!refreshToken.trim()) {
      setError('Please enter a refresh token')
      return
    }

    setImporting(true)
    setError(null)

    try {
      const res = await fetch('/api/oauth/kiro/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken: refreshToken.trim() }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Import failed')
      }

      // Success - notify parent to refresh connections
      onMethodSelect('import')
    } catch (err) {
      setError(err.message)
    } finally {
      setImporting(false)
    }
  }

  const handleIdcContinue = () => {
    if (!idcStartUrl.trim()) {
      setError('Please enter your IDC start URL')
      return
    }
    onMethodSelect('idc', { startUrl: idcStartUrl.trim(), region: idcRegion })
  }

  const handleSocialLogin = (provider) => {
    setSocialProvider(provider)
    setSocialOpen(true)
  }

  const handleSocialClose = () => {
    setSocialOpen(false)
    setSocialProvider(null)
    setSocialStep('loading')
    setSocialAuthUrl('')
    setSocialAuthData(null)
    setSocialCallbackUrl('')
    setSocialError(null)
  }

  const handleSocialSubmit = async () => {
    try {
      setSocialError(null)

      // Parse callback URL - can be either kiro:// or http://localhost format
      let url
      try {
        url = new URL(socialCallbackUrl)
      } catch {
        throw new Error('Invalid callback URL format')
      }

      const code = url.searchParams.get('code')
      const errorParam = url.searchParams.get('error')

      if (errorParam) {
        throw new Error(url.searchParams.get('error_description') || errorParam)
      }

      if (!code) {
        throw new Error('No authorization code found in URL')
      }

      // Exchange code for tokens
      const res = await fetch('/api/oauth/kiro/social-exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          codeVerifier: socialAuthData.codeVerifier,
          provider: socialProvider,
        }),
      })

      const data = await res.json()
      if (!res.ok) throw new Error(data.error)

      setSocialStep('success')
      // Notify parent
      onMethodSelect('social', { provider: socialProvider })
    } catch (err) {
      setSocialError(err.message)
      setSocialStep('error')
    }
  }

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedMethod(null)
      setError(null)
      setRefreshToken('')
      setIdcStartUrl('')
      setIdcRegion('us-east-1')
      setAutoDetected(false)
      handleSocialClose()
    }
  }, [isOpen])

  const socialProviderName = socialProvider === 'google' ? 'Google' : 'GitHub'

  return (
    <>
      <Modal isOpen={isOpen} title="Connect Kiro" onClose={onClose}>
        <div className="flex flex-col gap-4">
          {/* Method Selection */}
          {!selectedMethod && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-400 mb-2">
                Choose your authentication method:
              </p>

              {/* AWS Builder ID */}
              <button
                onClick={() => onMethodSelect('builder-id')}
                className="w-full p-4 text-left border border-zinc-700/50 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <Shield className="h-5 w-5 text-primary-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-zinc-100 mb-1">AWS Builder ID</h3>
                    <p className="text-sm text-zinc-400">
                      Recommended for most users. Free AWS account required.
                    </p>
                  </div>
                </div>
              </button>

              {/* AWS IAM Identity Center (IDC) */}
              <button
                onClick={() => handleMethodSelect('idc')}
                className="w-full p-4 text-left border border-zinc-700/50 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <Building2 className="h-5 w-5 text-primary-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-zinc-100 mb-1">AWS IAM Identity Center</h3>
                    <p className="text-sm text-zinc-400">
                      For enterprise users with custom AWS IAM Identity Center.
                    </p>
                  </div>
                </div>
              </button>

              {/* Google Social Login - HIDDEN */}
              <button
                onClick={() => handleSocialLogin('google')}
                className="hidden w-full p-4 text-left border border-zinc-700/50 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <Globe className="h-5 w-5 text-primary-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-zinc-100 mb-1">Google Account</h3>
                    <p className="text-sm text-zinc-400">
                      Login with your Google account (manual callback).
                    </p>
                  </div>
                </div>
              </button>

              {/* GitHub Social Login - HIDDEN */}
              <button
                onClick={() => handleSocialLogin('github')}
                className="hidden w-full p-4 text-left border border-zinc-700/50 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <Globe className="h-5 w-5 text-primary-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-zinc-100 mb-1">GitHub Account</h3>
                    <p className="text-sm text-zinc-400">
                      Login with your GitHub account (manual callback).
                    </p>
                  </div>
                </div>
              </button>

              {/* Import Token */}
              <button
                onClick={() => handleMethodSelect('import')}
                className="w-full p-4 text-left border border-zinc-700/50 rounded-lg hover:bg-zinc-800 transition-colors cursor-pointer"
              >
                <div className="flex items-start gap-3">
                  <Upload className="h-5 w-5 text-primary-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <h3 className="font-semibold text-zinc-100 mb-1">Import Token</h3>
                    <p className="text-sm text-zinc-400">
                      Paste refresh token from Kiro IDE.
                    </p>
                  </div>
                </div>
              </button>
            </div>
          )}

          {/* IDC Configuration */}
          {selectedMethod === 'idc' && (
            <div className="space-y-4">
              <Input
                label={
                  <span>
                    IDC Start URL <span className="text-red-500">*</span>
                  </span>
                }
                value={idcStartUrl}
                onChange={(e) => setIdcStartUrl(e.target.value)}
                placeholder="https://your-org.awsapps.com/start"
                className="font-mono text-sm"
              />
              <p className="text-xs text-zinc-500 -mt-2">
                Your organization&apos;s AWS IAM Identity Center URL
              </p>

              <Input
                label="AWS Region"
                value={idcRegion}
                onChange={(e) => setIdcRegion(e.target.value)}
                placeholder="us-east-1"
                className="font-mono text-sm"
              />
              <p className="text-xs text-zinc-500 -mt-2">
                AWS region for your Identity Center (default: us-east-1)
              </p>

              {error && (
                <p className="text-sm text-red-400">{error}</p>
              )}

              <div className="flex gap-2">
                <Button onClick={handleIdcContinue} className="flex-1">
                  Continue
                </Button>
                <Button onClick={handleBack} variant="ghost" className="flex-1">
                  Back
                </Button>
              </div>
            </div>
          )}

          {/* Import Token */}
          {selectedMethod === 'import' && (
            <div className="space-y-4">
              {/* Auto-detecting state */}
              {autoDetecting && (
                <div className="text-center py-6">
                  <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-primary-600/10 flex items-center justify-center">
                    <Loader2 className="h-8 w-8 text-primary-400 animate-spin" />
                  </div>
                  <h3 className="text-lg font-semibold text-zinc-100 mb-2">Auto-detecting token...</h3>
                  <p className="text-sm text-zinc-400">
                    Reading from AWS SSO cache
                  </p>
                </div>
              )}

              {/* Form (shown after auto-detect completes) */}
              {!autoDetecting && (
                <>
                  {/* Success message if auto-detected */}
                  {autoDetected && (
                    <div className="bg-green-900/20 p-3 rounded-lg border border-green-800/50">
                      <div className="flex gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-400 mt-0.5 shrink-0" />
                        <p className="text-sm text-green-300">
                          Token auto-detected from Kiro IDE successfully!
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Info message if not auto-detected */}
                  {!autoDetected && !error && (
                    <div className="bg-blue-900/20 p-3 rounded-lg border border-blue-800/50">
                      <div className="flex gap-2">
                        <AlertCircle className="h-4 w-4 text-blue-400 mt-0.5 shrink-0" />
                        <p className="text-sm text-blue-300">
                          Kiro IDE not detected. Please paste your refresh token manually.
                        </p>
                      </div>
                    </div>
                  )}

                  <Input
                    label={
                      <span>
                        Refresh Token <span className="text-red-500">*</span>
                      </span>
                    }
                    value={refreshToken}
                    onChange={(e) => setRefreshToken(e.target.value)}
                    placeholder="Token will be auto-filled..."
                    className="font-mono text-sm"
                  />

                  {error && (
                    <div className="bg-red-900/20 p-3 rounded-lg border border-red-800/50">
                      <p className="text-sm text-red-400">{error}</p>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <Button
                      onClick={handleImportToken}
                      className="flex-1"
                      disabled={importing || !refreshToken.trim()}
                    >
                      {importing ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Importing...
                        </>
                      ) : (
                        'Import Token'
                      )}
                    </Button>
                    <Button onClick={handleBack} variant="ghost" className="flex-1">
                      Back
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* Social OAuth Sub-Modal */}
      <Modal
        isOpen={socialOpen}
        title={`Connect Kiro via ${socialProviderName}`}
        onClose={handleSocialClose}
      >
        <div className="flex flex-col gap-4">
          {/* Loading */}
          {socialStep === 'loading' && (
            <div className="text-center py-6">
              <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-primary-600/10 flex items-center justify-center">
                <Loader2 className="h-8 w-8 text-primary-400 animate-spin" />
              </div>
              <h3 className="text-lg font-semibold text-zinc-100 mb-2">Initializing...</h3>
              <p className="text-sm text-zinc-400">
                Setting up {socialProviderName} authentication
              </p>
            </div>
          )}

          {/* Manual Input Step */}
          {socialStep === 'input' && (
            <>
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-zinc-200 mb-2">Step 1: Open this URL in your browser</p>
                  <div className="flex gap-2">
                    <Input value={socialAuthUrl} readOnly className="flex-1 font-mono text-xs" />
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => handleCopy(socialAuthUrl, 'auth_url')}
                      disabled={!socialAuthUrl}
                    >
                      {copiedField === 'auth_url' ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                      Copy
                    </Button>
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-zinc-200 mb-2">Step 2: Paste the callback URL here</p>
                  <p className="text-xs text-zinc-500 mb-2">
                    After authorization, copy the full URL from your browser address bar.
                  </p>
                  <Input
                    value={socialCallbackUrl}
                    onChange={(e) => setSocialCallbackUrl(e.target.value)}
                    placeholder="kiro://kiro.kiroAgent/authenticate-success?code=..."
                    className="font-mono text-xs"
                  />
                </div>
              </div>

              {socialError && (
                <div className="bg-red-900/20 p-3 rounded-lg border border-red-800/50">
                  <p className="text-sm text-red-400">{socialError}</p>
                </div>
              )}

              <div className="flex gap-2">
                <Button onClick={handleSocialSubmit} className="flex-1" disabled={!socialCallbackUrl}>
                  Connect
                </Button>
                <Button onClick={handleSocialClose} variant="ghost" className="flex-1">
                  Cancel
                </Button>
              </div>
            </>
          )}

          {/* Success */}
          {socialStep === 'success' && (
            <div className="text-center py-6">
              <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-green-900/30 flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-zinc-100 mb-2">Connected Successfully!</h3>
              <p className="text-sm text-zinc-400 mb-4">
                Your Kiro account via {socialProviderName} has been connected.
              </p>
              <Button onClick={handleSocialClose} className="w-full">
                Done
              </Button>
            </div>
          )}

          {/* Error */}
          {socialStep === 'error' && (
            <div className="text-center py-6">
              <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-red-900/30 flex items-center justify-center">
                <AlertCircle className="h-8 w-8 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-zinc-100 mb-2">Connection Failed</h3>
              <p className="text-sm text-red-400 mb-4">{socialError}</p>
              <div className="flex gap-2">
                <Button onClick={() => setSocialStep('input')} variant="secondary" className="flex-1">
                  Try Again
                </Button>
                <Button onClick={handleSocialClose} variant="ghost" className="flex-1">
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </>
  )
}
