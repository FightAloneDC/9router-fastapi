/**
 * Shared WebSocket for /api/usage/ws.
 *
 * Replaces EventSource SSE (/usage/stream), which Firefox aborted under
 * StrictMode remounts. Same pattern as consoleStream.js: one shared socket,
 * deferred close so remount reuses the connection. No polling.
 */

let sharedSocket = null
let sharedToken = null
let refCount = 0
let closeTimer = null
let reconnectTimer = null
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

function wsUrl(token) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const q = encodeURIComponent(token)
  return `${proto}//${window.location.host}/api/usage/ws?token=${q}`
}

function clearReconnectTimer() {
  if (!reconnectTimer) return
  clearTimeout(reconnectTimer)
  reconnectTimer = null
}

function clearCloseTimer() {
  if (!closeTimer) return
  clearTimeout(closeTimer)
  closeTimer = null
}

function ensureConnected(token) {
  if (!token) return

  if (
    sharedSocket &&
    sharedToken === token &&
    (sharedSocket.readyState === WebSocket.OPEN ||
      sharedSocket.readyState === WebSocket.CONNECTING)
  ) {
    return
  }

  if (sharedSocket) {
    sharedSocket.onclose = null
    sharedSocket.onerror = null
    sharedSocket.onmessage = null
    sharedSocket.close()
    sharedSocket = null
  }

  sharedToken = token
  const socket = new WebSocket(wsUrl(token))
  sharedSocket = socket

  socket.onmessage = (event) => {
    try {
      dispatch(JSON.parse(event.data))
    } catch {
      // ignore parse errors
    }
  }

  socket.onerror = () => {
    // onclose handles reconnect
  }

  socket.onclose = () => {
    if (sharedSocket === socket) {
      sharedSocket = null
    }
    if (refCount <= 0) return

    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (refCount > 0 && sharedToken) {
        ensureConnected(sharedToken)
      }
    }, 5000)
  }
}

/**
 * Subscribe to usage WebSocket updates.
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

  clearCloseTimer()
  clearReconnectTimer()
  ensureConnected(token)

  return () => {
    listeners.delete(onData)
    refCount = Math.max(0, refCount - 1)

    if (refCount > 0) return

    clearReconnectTimer()

    // Defer close so StrictMode remount can reuse the socket.
    clearCloseTimer()
    closeTimer = setTimeout(() => {
      closeTimer = null
      if (refCount > 0) return
      if (sharedSocket) {
        sharedSocket.onclose = null
        sharedSocket.onerror = null
        sharedSocket.onmessage = null
        sharedSocket.close()
        sharedSocket = null
      }
      sharedToken = null
    }, 50)
  }
}
