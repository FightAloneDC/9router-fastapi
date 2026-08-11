/**
 * Shared WebSocket for /api/console/ws.
 *
 * React StrictMode (dev) mounts → unmounts → remounts effects in one
 * turn. Closing the socket in cleanup then reopening causes Firefox
 * "can't establish / interrupted while loading" noise. Delay teardown
 * so a remount reuses the same connection.
 */

let sharedSocket = null
let refCount = 0
let closeTimer = null
let reconnectTimer = null
const listeners = new Set()
const statusListeners = new Set()

function dispatchStatus(connected) {
  for (const listener of statusListeners) {
    try {
      listener(connected)
    } catch {
      // ignore listener errors
    }
  }
}

function dispatchMessage(data) {
  for (const listener of listeners) {
    try {
      listener(data)
    } catch {
      // ignore listener errors
    }
  }
}

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/console/ws`
}

function clearReconnectTimer() {
  if (!reconnectTimer) return
  clearTimeout(reconnectTimer)
  reconnectTimer = null
}

function ensureConnected() {
  if (
    sharedSocket &&
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

  const socket = new WebSocket(wsUrl())
  sharedSocket = socket

  socket.onopen = () => {
    if (sharedSocket === socket) {
      dispatchStatus(true)
    }
  }

  socket.onmessage = (event) => {
    try {
      dispatchMessage(JSON.parse(event.data))
    } catch {
      // ignore parse errors
    }
  }

  socket.onerror = () => {
    // onclose handles reconnect / status
  }

  socket.onclose = () => {
    if (sharedSocket === socket) {
      sharedSocket = null
    }
    dispatchStatus(false)

    if (refCount <= 0) return

    clearReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (refCount > 0) {
        ensureConnected()
      }
    }, 5000)
  }
}

/**
 * Subscribe to console WebSocket log entries.
 * @param {(entry: object) => void} onEntry
 * @param {(connected: boolean) => void} [onStatus]
 * @returns {() => void} unsubscribe
 */
export function subscribeConsoleStream(onEntry, onStatus) {
  if (typeof onEntry !== 'function') {
    return () => {}
  }

  listeners.add(onEntry)
  if (typeof onStatus === 'function') {
    statusListeners.add(onStatus)
  }
  refCount += 1

  if (closeTimer) {
    clearTimeout(closeTimer)
    closeTimer = null
  }
  clearReconnectTimer()

  ensureConnected()

  if (
    sharedSocket &&
    sharedSocket.readyState === WebSocket.OPEN &&
    typeof onStatus === 'function'
  ) {
    onStatus(true)
  }

  return () => {
    listeners.delete(onEntry)
    if (typeof onStatus === 'function') {
      statusListeners.delete(onStatus)
    }
    refCount = Math.max(0, refCount - 1)

    if (refCount > 0) return

    clearReconnectTimer()

    // Defer close so StrictMode remount can reuse the socket.
    if (closeTimer) clearTimeout(closeTimer)
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
      dispatchStatus(false)
    }, 50)
  }
}
