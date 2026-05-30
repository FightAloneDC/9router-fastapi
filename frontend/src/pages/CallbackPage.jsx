import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, CheckCircle, Info } from 'lucide-react'

function CallbackContent() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState('processing')

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const error = searchParams.get('error')
    const errorDescription = searchParams.get('error_description')

    const callbackData = {
      code,
      state,
      error,
      errorDescription,
      fullUrl: window.location.href,
    }

    let relayed = false

    // Trusted origins that may receive this callback
    const expectedOrigins = [
      window.location.origin,
      'http://localhost:1455',
    ]

    // Method 1: postMessage to opener (popup mode)
    if (window.opener) {
      for (const origin of expectedOrigins) {
        try {
          window.opener.postMessage({ type: 'oauth_callback', data: callbackData }, origin)
          relayed = true
        } catch (e) {
          console.log('postMessage failed:', e)
        }
      }
    }

    // Method 2: BroadcastChannel (same origin tabs)
    try {
      const channel = new BroadcastChannel('oauth_callback')
      channel.postMessage(callbackData)
      channel.close()
      relayed = true
    } catch (e) {
      console.log('BroadcastChannel failed:', e)
    }

    // Method 3: localStorage event (fallback)
    try {
      localStorage.setItem('oauth_callback', JSON.stringify({ ...callbackData, timestamp: Date.now() }))
      relayed = true
    } catch (e) {
      console.log('localStorage failed:', e)
    }

    if (!(code || error)) {
      setTimeout(() => setStatus('manual'), 0)
      return
    }

    setStatus('success')
    setTimeout(() => {
      window.close()
      setTimeout(() => setStatus('done'), 500)
    }, 1500)
  }, [searchParams])

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900">
      <div className="text-center p-8 max-w-md">
        {status === 'processing' && (
          <>
            <div className="size-16 mx-auto mb-4 rounded-full bg-blue-500/10 flex items-center justify-center">
              <Loader2 className="size-8 text-blue-500 animate-spin" />
            </div>
            <h1 className="text-xl font-semibold mb-2">Processing...</h1>
            <p className="text-slate-400">Please wait while we complete the authorization.</p>
          </>
        )}

        {(status === 'success' || status === 'done') && (
          <>
            <div className="size-16 mx-auto mb-4 rounded-full bg-green-900/30 flex items-center justify-center">
              <CheckCircle className="size-8 text-green-400" />
            </div>
            <h1 className="text-xl font-semibold mb-2">Authorization Successful!</h1>
            <p className="text-slate-400">
              {status === 'success' ? 'This window will close automatically...' : 'You can close this tab now.'}
            </p>
          </>
        )}

        {status === 'manual' && (
          <>
            <div className="size-16 mx-auto mb-4 rounded-full bg-yellow-900/30 flex items-center justify-center">
              <Info className="size-8 text-yellow-400" />
            </div>
            <h1 className="text-xl font-semibold mb-2">Copy This URL</h1>
            <p className="text-slate-400 mb-4">
              Please copy the URL from the address bar and paste it in the application.
            </p>
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-left">
              <code className="text-xs break-all">{typeof window !== 'undefined' ? window.location.href : ''}</code>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function CallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center p-8">
          <div className="size-16 mx-auto mb-4 rounded-full bg-blue-500/10 flex items-center justify-center">
            <Loader2 className="size-8 text-blue-500 animate-spin" />
          </div>
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    }>
      <CallbackContent />
    </Suspense>
  )
}
