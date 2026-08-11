/**
 * Shared EventSource for /api/usage/stream.
 *
 * React StrictMode (dev) mounts → unmounts → remounts effects in one
 * turn. Closing the socket in cleanup then reopening causes a cancelled
 * ("Blocked") request in DevTools. Delay teardown so a remount reuses
 * the same connection.
 */

let sharedSource = null
let sharedToken = null
let refCount = 0
let closeTimer = null
const listeners = new Set()

function dispatch(data) {
  for (const listener of listeners) {
    try {
      listener(data)
    } catch {
      // ignore listener errors
    }
  }
}

function ensureConnected(token) {
  if (
    sharedSource &&
    sharedToken === token &&
    sharedSource.readyState !== EventSource.CLOSED
  ) {
    return
  }

  if (sharedSource) {
    sharedSource.close()
    sharedSource = null
  }

  sharedToken = token
  const source = new EventSource(
    `/api/usage/stream?token=${encodeURIComponent(token)}`
  )
  sharedSource = source

  const onPayload = (e) => {
    try {
      dispatch(JSON.parse(e.data || '{}'))
    } catch {
      // ignore parse errors
    }
  }

  source.addEventListener('update', onPayload)
  source.addEventListener('keepalive', onPayload)

  source.onerror = () => {
    source.close()
    if (sharedSource === source) {
      sharedSource = null
    }
    // Auto-reconnect while subscribers remain
    if (refCount > 0 && sharedToken) {
      if (closeTimer) clearTimeout(closeTimer)
      closeTimer = setTimeout(() => {
        closeTimer = null
        if (refCount > 0 && sharedToken) {
          ensureConnected(sharedToken)
        }
      }, 5000)
    }
  }
}

/**
 * Subscribe to usage SSE updates.
 * @param {string} token JWT
 * @param {(data: object) => void} onData
 * @returns {() => void} unsubscribe
 */
export function subscribeUsageStream(token, onData) {
  if (!token || typeof onData !== 'function') {
    return () => {}
  }

  listeners.add(onData)
  refCount += 1

  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }

  ensureConnected(token)

  return () => {
    listeners.delete(onData)
    refCount = Math.max(0, refCount - 1)

    if (refCount > 0) return

    // Defer close so StrictMode remount can reuse the socket.
    if (closeTimer) clearTimeout(closeTimer)
    closeTimer = setTimeout(() => {
      closeTimer = null
      if (refCount > 0) return
      if (sharedSource) {
        sharedSource.close()
        sharedSource = null
      }
      sharedToken = null
    }, 50)
  }
}
