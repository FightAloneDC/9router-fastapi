import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Copy,
  ExternalLink,
  Check,
  Key,
} from 'lucide-react'
import Modal from './ui/Modal'
import Button from './ui/Button'
import Input from './ui/Input'
import useCatalogStore from '../stores/catalogStore'

export default function OAuthModal({
  isOpen,
  provider,
  providerInfo,
  onSuccess,
  onClose,
  oauthMeta,
  idcConfig,
}) {
  const [step, setStep] = useState('waiting')
  const [authData, setAuthData] = useState(null)
  const [callbackUrl, setCallbackUrl] = useState('')
  const [error, setError] = useState(null)
  const [isDeviceCode, setIsDeviceCode] = useState(false)
  const [deviceData, setDeviceData] = useState(null)
  const [polling, setPolling] = useState(false)
  const [copiedField, setCopiedField] = useState(null)
  const [isLocalhost, setIsLocalhost] = useState(false)
  const [placeholderUrl, setPlaceholderUrl] = useState('/callback?code=...')
  const [authMethod, setAuthMethod] = useState(null) // null = not chosen, 'device' = device flow, 'pat' = PAT import
  const [patToken, setPatToken] = useState('')
  const [importingPat, setImportingPat] = useState(false)

  const popupRef = useRef(null)
  const pollingAbortRef = useRef(false)
  const callbackProcessedRef = useRef(false)

  const handleCopy = useCallback(async (text, field) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch {
      // clipboard not available
    }
  }, [])

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsLocalhost(
        window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      )
      setPlaceholderUrl(`${window.location.origin}/callback?code=...`)
    }
  }, [])

  const exchangeTokens = useCallback(
    async (code, state) => {
      if (!authData) return
      try {
        const res = await fetch(`/api/oauth/${provider}/exchange`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code,
            redirectUri: authData.redirectUri,
            codeVerifier: authData.codeVerifier,
            state,
            ...(oauthMeta ? { meta: oauthMeta } : {}),
          }),
        })

        const data = await res.json()
        if (!res.ok) throw new Error(data.error)

        setStep('success')
        onSuccess?.()
      } catch (err) {
        setError(err.message)
        setStep('error')
      }
    },
    [authData, provider, onSuccess, oauthMeta]
  )

  const importPAT = useCallback(async () => {
    if (!patToken.trim()) return
    setImportingPat(true)
    setError(null)
    try {
      const res = await fetch(`/api/oauth/${provider}/pat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ personalToken: patToken.trim() }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || data.error || 'PAT import failed')
      setStep('success')
      onSuccess?.()
    } catch (err) {
      setError(err.message)
      setStep('error')
    } finally {
      setImportingPat(false)
    }
  }, [patToken, provider, onSuccess])

  const startPolling = useCallback(
    async (deviceCode, codeVerifier, interval, extraData) => {
      pollingAbortRef.current = false
      setPolling(true)
      const maxAttempts = 60

      for (let i = 0; i < maxAttempts; i++) {
        if (pollingAbortRef.current) {
          setPolling(false)
          return
        }

        await new Promise((r) => setTimeout(r, interval * 1000))

        if (pollingAbortRef.current) {
          setPolling(false)
          return
        }

        try {
          const res = await fetch(`/api/oauth/${provider}/poll`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deviceCode, codeVerifier, extraData }),
          })

          const data = await res.json()

          if (data.success) {
            pollingAbortRef.current = true
            setStep('success')
            setPolling(false)
            onSuccess?.()
            return
          }

          if (data.error === 'expired_token' || data.error === 'access_denied') {
            throw new Error(data.errorDescription || data.error)
          }

          if (data.error === 'slow_down') {
            interval = Math.min(interval + 5, 30)
          }
        } catch (err) {
          setError(err.message)
          setStep('error')
          setPolling(false)
          return
        }
      }

      setError('Authorization timeout')
      setStep('error')
      setPolling(false)
    },
    [provider, onSuccess]
  )

  const startOAuthFlow = useCallback(async (method = null) => {
    const effectiveMethod = method || authMethod
    if (!provider) return
    const catalogEntry = useCatalogStore.getState().providers[provider] || {}
    const flowType = catalogEntry.flowType
    const supportsPAT = catalogEntry.supportsPAT
    const requiresProxy = catalogEntry.requiresProxy
    try {
      setError(null)

      // Providers that support PAT: show choice first
      if (supportsPAT && effectiveMethod === null) {
        setStep('choose')
        return
      }

      // Device code flow (data-driven)
      if (flowType === 'device_code') {
        setIsDeviceCode(true)
        setStep('waiting')

        const deviceCodeUrl = new URL(
          `/api/oauth/${provider}/device-code`,
          window.location.origin
        )
        // Generic: pass any device code options (e.g. idcConfig for Kiro)
        if (idcConfig?.startUrl) {
          deviceCodeUrl.searchParams.set('start_url', idcConfig.startUrl)
          if (idcConfig.region) {
            deviceCodeUrl.searchParams.set('region', idcConfig.region)
          }
          deviceCodeUrl.searchParams.set('auth_method', 'idc')
        }
        const res = await fetch(deviceCodeUrl.toString())
        const data = await res.json()
        if (!res.ok) throw new Error(data.error)

        setDeviceData(data)

        const verifyUrl = data.verification_uri_complete || data.verification_uri
        if (verifyUrl) window.open(verifyUrl, '_blank', 'noopener,noreferrer')

        // Generic: collect all _ prefixed keys from response + data.extra
        const extraData = {}
        for (const [key, val] of Object.entries(data)) {
          if (key.startsWith('_')) extraData[key] = val
        }
        if (data.extra) {
          for (const [key, val] of Object.entries(data.extra)) {
            if (key.startsWith('_')) extraData[key] = val
          }
        }
        // Qoder: codeVerifier is used as _qoderVerifier
        if (data.codeVerifier) {
          extraData._qoderVerifier = data.codeVerifier
        }

        startPolling(data.device_code, data.codeVerifier, data.interval || 5, Object.keys(extraData).length ? extraData : null)
        return
      }

      // Authorization code flow (with or without PKCE)
      const appPort = window.location.port || (window.location.protocol === 'https:' ? '443' : '80')
      const redirectUri = requiresProxy
        ? 'http://localhost:1455/auth/callback'
        : `http://localhost:${appPort}/callback`

      const authorizeUrl = new URL(
        `/api/oauth/${provider}/authorize`,
        window.location.origin
      )
      authorizeUrl.searchParams.set('redirect_uri', redirectUri)
      if (oauthMeta) {
        Object.entries(oauthMeta).forEach(([k, v]) => {
          if (v) authorizeUrl.searchParams.set(k, v)
        })
      }
      const res = await fetch(authorizeUrl.toString())
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)

      // Proxy providers (e.g. codex) start a local proxy server
      let codexProxyActive = false
      let codexServerSide = false
      if (requiresProxy) {
        try {
          const proxyUrl = new URL(`/api/oauth/codex/start-proxy`, window.location.origin)
          proxyUrl.searchParams.set('app_port', appPort)
          proxyUrl.searchParams.set('state', data.state)
          proxyUrl.searchParams.set('code_verifier', data.codeVerifier)
          proxyUrl.searchParams.set('redirect_uri', redirectUri)
          const proxyRes = await fetch(proxyUrl.toString())
          const proxyData = await proxyRes.json()
          codexProxyActive = proxyData.success
          codexServerSide = !!proxyData.serverSide
        } catch {
          codexProxyActive = false
        }
      }

      setAuthData({ ...data, redirectUri, codexServerSide })

      if (requiresProxy && codexProxyActive) {
        setStep('waiting')
        popupRef.current = window.open(data.authUrl, 'oauth_popup', 'width=600,height=700')
        if (!popupRef.current) {
          setStep('input')
        }
      } else if (!isLocalhost || requiresProxy) {
        setStep('input')
        window.open(data.authUrl, '_blank')
      } else {
        setStep('waiting')
        popupRef.current = window.open(data.authUrl, 'oauth_popup', 'width=600,height=700')
        if (!popupRef.current) {
          setStep('input')
        }
      }
    } catch (err) {
      console.error('[Qoder OAuth] Error in startOAuthFlow:', err)
      setError(err.message)
      setStep('error')
    }
  }, [provider, isLocalhost, startPolling, oauthMeta, idcConfig, authMethod])

  useEffect(() => {
    if (isOpen && provider) {
      setAuthData(null)
      setCallbackUrl('')
      setError(null)
      setIsDeviceCode(false)
      setDeviceData(null)
      setPolling(false)
      setAuthMethod(null)
      setPatToken('')
      pollingAbortRef.current = false
      callbackProcessedRef.current = false
      startOAuthFlow()
    } else if (!isOpen) {
      pollingAbortRef.current = true
      const entry = useCatalogStore.getState().providers[provider]
      if (entry?.requiresProxy) {
        fetch('/api/oauth/codex/stop-proxy').catch(() => {})
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, provider])

  useEffect(() => {
    if (!authData?.codexServerSide || !authData?.state) return
    if (callbackProcessedRef.current) return
    let cancelled = false
    const POLL_INTERVAL_MS = 1500
    const MAX_ATTEMPTS = 200
    let attempts = 0

    const tick = async () => {
      if (cancelled || callbackProcessedRef.current) return
      attempts += 1
      try {
        const res = await fetch(
          `/api/oauth/codex/poll-status?state=${encodeURIComponent(authData.state)}`
        )
        const data = await res.json()
        if (cancelled || callbackProcessedRef.current) return
        if (data.status === 'done') {
          callbackProcessedRef.current = true
          setStep('success')
          onSuccess?.()
          return
        }
        if (data.status === 'error') {
          callbackProcessedRef.current = true
          setError(data.error || 'Authentication failed')
          setStep('error')
          return
        }
      } catch {
        // Network error, keep polling
      }
      if (attempts >= MAX_ATTEMPTS) {
        callbackProcessedRef.current = true
        setError('Authentication timeout')
        setStep('error')
        return
      }
      setTimeout(tick, POLL_INTERVAL_MS)
    }
    setTimeout(tick, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
    }
  }, [authData, onSuccess])

  useEffect(() => {
    if (!authData) return
    callbackProcessedRef.current = false

    const handleCallback = async (data) => {
      if (callbackProcessedRef.current) return

      const { code, state, error: callbackError, errorDescription } = data

      if (callbackError) {
        callbackProcessedRef.current = true
        setError(errorDescription || callbackError)
        setStep('error')
        return
      }

      if (code) {
        callbackProcessedRef.current = true
        await exchangeTokens(code, state)
      }
    }

    const handleMessage = (event) => {
      const isLocal =
        event.origin.includes('localhost') || event.origin.includes('127.0.0.1')
      const isSameOrigin = event.origin === window.location.origin
      if (!isLocal && !isSameOrigin) return

      if (event.data?.type === 'oauth_callback') {
        handleCallback(event.data.data)
      }
    }
    window.addEventListener('message', handleMessage)

    let channel
    try {
      channel = new BroadcastChannel('oauth_callback')
      channel.onmessage = (event) => handleCallback(event.data)
    } catch {
      // BroadcastChannel not supported
    }

    const handleStorage = (event) => {
      if (event.key === 'oauth_callback' && event.newValue) {
        try {
          const data = JSON.parse(event.newValue)
          handleCallback(data)
          localStorage.removeItem('oauth_callback')
        } catch {
          // Failed to parse
        }
      }
    }
    window.addEventListener('storage', handleStorage)

    try {
      const stored = localStorage.getItem('oauth_callback')
      if (stored) {
        const data = JSON.parse(stored)
        if (data.timestamp && Date.now() - data.timestamp < 30000) {
          handleCallback(data)
        }
        localStorage.removeItem('oauth_callback')
      }
    } catch {
      // localStorage unavailable
    }

    return () => {
      window.removeEventListener('message', handleMessage)
      window.removeEventListener('storage', handleStorage)
      if (channel) channel.close()
    }
  }, [authData, exchangeTokens])

  const handleManualSubmit = async () => {
    try {
      setError(null)
      const url = new URL(callbackUrl)
      const code = url.searchParams.get('code')
      const state = url.searchParams.get('state')
      const errorParam = url.searchParams.get('error')

      if (errorParam) {
        throw new Error(url.searchParams.get('error_description') || errorParam)
      }

      if (!code) {
        throw new Error('No authorization code found in URL')
      }

      await exchangeTokens(code, state)
    } catch (err) {
      setError(err.message)
      setStep('error')
    }
  }

  const handleClose = useCallback(() => {
    const entry = useCatalogStore.getState().providers[provider]
    if (entry?.requiresProxy) {
      fetch('/api/oauth/codex/stop-proxy').catch(() => {})
    }
    onClose()
  }, [onClose, provider])

  if (!provider || !providerInfo) return null

  const deviceLoginUrl =
    deviceData?.verification_uri_complete || deviceData?.verification_uri || ''

  return (
    <Modal isOpen={isOpen} title={`Connect ${providerInfo.name}`} onClose={handleClose}>
      <div className="flex flex-col gap-4">
        {(step === 'waiting' || step === 'input') && !isDeviceCode && (
          <>
            <div className="flex items-center gap-2 px-3 py-2 border border-zinc-700/50 rounded-lg bg-zinc-800">
              <Loader2 className="h-4 w-4 text-zinc-400 animate-spin" />
              <span className="text-sm text-zinc-300">
                Waiting for popup authorization...
              </span>
            </div>

            <div className="flex items-center gap-3 my-1">
              <div className="flex-1 h-px bg-zinc-700/50" />
              <span className="text-xs text-zinc-500 uppercase tracking-wider">
                Or paste callback URL manually
              </span>
              <div className="flex-1 h-px bg-zinc-700/50" />
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-zinc-200 mb-2">
                  Step 1: Open this URL in your browser
                </p>
                <div className="flex gap-2">
                  <Input
                    value={authData?.authUrl || ''}
                    readOnly
                    className="flex-1 font-mono text-xs"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleCopy(authData?.authUrl, 'auth_url')}
                    disabled={!authData?.authUrl}
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
                <p className="text-sm font-medium text-zinc-200 mb-2">
                  Step 2: Paste the callback URL here
                </p>
                <p className="text-xs text-zinc-500 mb-2">
                  After authorization, copy the full URL from your browser.
                </p>
                <Input
                  value={callbackUrl}
                  onChange={(e) => setCallbackUrl(e.target.value)}
                  placeholder={placeholderUrl}
                  className="font-mono text-xs"
                />
              </div>
            </div>

            <div className="flex gap-2">
              <Button onClick={handleManualSubmit} fullWidth disabled={!callbackUrl}>
                Connect
              </Button>
              <Button onClick={handleClose} variant="ghost" fullWidth>
                Cancel
              </Button>
            </div>
          </>
        )}

        {step === 'waiting' && isDeviceCode && deviceData && (
          <>
            <div className="text-center py-4">
              <p className="text-sm text-zinc-500 mb-4">
                Visit the login URL below and authorize:
              </p>
              <div className="bg-zinc-800 p-4 rounded-lg mb-4">
                <p className="text-xs text-zinc-500 mb-1">Login URL</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-sm text-zinc-300 break-all">
                    {deviceLoginUrl}
                  </code>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleCopy(deviceLoginUrl, 'login_url')}
                    disabled={!deviceLoginUrl}
                  >
                    {copiedField === 'login_url' ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      window.open(deviceLoginUrl, '_blank', 'noopener,noreferrer')
                    }
                    disabled={!deviceLoginUrl}
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open
                  </Button>
                </div>
              </div>
              <div className="bg-zinc-800 p-4 rounded-lg">
                <p className="text-xs text-zinc-500 mb-1">Your Code</p>
                <div className="flex items-center justify-center gap-2">
                  <p className="text-2xl font-mono font-bold text-zinc-100">
                    {deviceData.user_code}
                  </p>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleCopy(deviceData.user_code, 'user_code')}
                  >
                    {copiedField === 'user_code' ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
            {polling && (
              <div className="flex items-center justify-center gap-2 text-sm text-zinc-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Waiting for authorization...
              </div>
            )}
          </>
        )}

        {step === 'choose' && (
          <div className="flex flex-col gap-4 py-4">
            <p className="text-sm text-zinc-400 text-center">
              Choose authentication method:
            </p>
            <Button
              onClick={() => {
                console.log('[Qoder OAuth] Button clicked - starting device flow')
                setAuthMethod('device')
                startOAuthFlow('device')
              }}
              fullWidth
            >
              <ExternalLink className="h-4 w-4 mr-2" />
              OAuth Device Flow
            </Button>
            <Button
              onClick={() => {
                setAuthMethod('pat')
                setStep('pat')
              }}
              variant="secondary"
              fullWidth
            >
              <Key className="h-4 w-4 mr-2" />
              Import Personal Access Token
            </Button>
            <p className="text-xs text-zinc-500 text-center">
              Get your PAT from{' '}
              <a
                href="https://qoder.com/account/integrations"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-400 hover:underline"
              >
                qoder.com/account/integrations
              </a>
            </p>
            <Button onClick={handleClose} variant="ghost" fullWidth>
              Cancel
            </Button>
          </div>
        )}

        {step === 'pat' && (
          <div className="flex flex-col gap-4 py-4">
            <div>
              <p className="text-sm font-medium text-zinc-200 mb-2">
                Personal Access Token
              </p>
              <p className="text-xs text-zinc-500 mb-3">
                Paste your PAT from{' '}
                <a
                  href="https://qoder.com/account/integrations"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:underline"
                >
                  qoder.com/account/integrations
                </a>
              </p>
              <Input
                type="password"
                value={patToken}
                onChange={(e) => setPatToken(e.target.value)}
                placeholder="pt-..."
                className="font-mono text-xs"
              />
            </div>
            {error && (
              <div className="rounded-lg border p-3 bg-red-950/30 border-red-700/40">
                <div className="flex items-center gap-2">
                  <AlertCircle size={16} className="text-red-400 shrink-0" />
                  <span className="text-sm text-red-300">{error}</span>
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button
                onClick={importPAT}
                fullWidth
                disabled={!patToken.trim() || importingPat}
              >
                {importingPat ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Importing...
                  </>
                ) : (
                  'Import PAT'
                )}
              </Button>
              <Button
                onClick={() => {
                  setAuthMethod(null)
                  setStep('choose')
                  setError(null)
                }}
                variant="ghost"
                fullWidth
              >
                Back
              </Button>
            </div>
          </div>
        )}

        {step === 'success' && (
          <div className="text-center py-6">
            <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-green-900/30 flex items-center justify-center">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">
              Connected Successfully!
            </h3>
            <p className="text-sm text-zinc-500 mb-4">
              Your {providerInfo.name} account has been connected.
            </p>
            <Button onClick={handleClose} fullWidth>
              Done
            </Button>
          </div>
        )}

        {step === 'error' && (
          <div className="text-center py-6">
            <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-red-900/30 flex items-center justify-center">
              <AlertCircle className="h-8 w-8 text-red-600" />
            </div>
            <h3 className="text-lg font-semibold text-zinc-100 mb-2">
              Connection Failed
            </h3>
            <p className="text-sm text-red-600 mb-4">{error}</p>
            <div className="flex gap-2">
              <Button onClick={startOAuthFlow} variant="secondary" fullWidth>
                Try Again
              </Button>
              <Button onClick={handleClose} variant="ghost" fullWidth>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
