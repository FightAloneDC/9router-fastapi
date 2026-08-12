/**
 * WebSocket client for /api/providers/bulk-jobs/ws.
 *
 * One socket per active jobId. StrictMode-safe deferred teardown
 * (same pattern as usageStream.js / consoleStream.js). Reconnects
 * until unsubscribe or a terminal event (done / error).
 */

/** @typedef {object} JobStreamState */
/** @type {Map<string, JobStreamState>} */
const jobs = new Map()
const MAX_RECONNECT_ATTEMPTS = 3

function createJobState() {
  return {
    socket: null,
    token: null,
    refCount: 0,
    closeTimer: null,
    reconnectTimer: null,
    listeners: new Set(),
    terminal: false,
    reconnectAttempts: 0,
  }
}

function getJobState(jobId) {
  if (!jobs.has(jobId)) {
    jobs.set(jobId, createJobState())
  }
  return jobs.get(jobId)
}

function wsUrl(token, jobId) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const q = encodeURIComponent(token)
  const j = encodeURIComponent(jobId)
  return (
    `${proto}//${window.location.host}` +
    `/api/providers/bulk-jobs/ws?token=${q}&jobId=${j}`
  )
}

function clearReconnectTimer(state) {
  if (!state.reconnectTimer) return
  clearTimeout(state.reconnectTimer)
  state.reconnectTimer = null
}

function clearCloseTimer(state) {
  if (!state.closeTimer) return
  clearTimeout(state.closeTimer)
  state.closeTimer = null
}

function closeSocket(state) {
  if (!state.socket) return
  state.socket.onclose = null
  state.socket.onerror = null
  state.socket.onmessage = null
  state.socket.close()
  state.socket = null
}

function dispatch(jobId, data) {
  const state = jobs.get(jobId)
  if (!state) return
  for (const listener of state.listeners) {
    try {
      listener(data)
    } catch {
      // ignore listener errors
    }
  }
}

function markTerminalIfNeeded(jobId, data) {
  if (data?.type !== 'done' && data?.type !== 'error') return
  const state = jobs.get(jobId)
  if (!state) return
  state.terminal = true
  clearReconnectTimer(state)
}

function endWithError(jobId, message) {
  const state = jobs.get(jobId)
  if (!state || state.terminal) return
  state.terminal = true
  clearReconnectTimer(state)
  dispatch(jobId, { type: 'error', jobId, message })
}

function ensureConnected(jobId, token) {
  const state = getJobState(jobId)
  if (!token || state.terminal) return

  if (
    state.socket &&
    state.token === token &&
    (state.socket.readyState === WebSocket.OPEN ||
      state.socket.readyState === WebSocket.CONNECTING)
  ) {
    return
  }

  closeSocket(state)
  state.token = token
  const socket = new WebSocket(wsUrl(token, jobId))
  state.socket = socket

  socket.onopen = () => {
    state.reconnectAttempts = 0
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      markTerminalIfNeeded(jobId, data)
      dispatch(jobId, data)
    } catch {
      // ignore parse errors
    }
  }

  socket.onerror = () => {
    // onclose handles reconnect
  }

  socket.onclose = (event) => {
    if (state.socket === socket) {
      state.socket = null
    }
    if (state.refCount <= 0 || state.terminal) return
    if (event.code === 1008) {
      endWithError(jobId, 'Bulk job stream is no longer available.')
      return
    }
    if (state.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      endWithError(jobId, 'Unable to reconnect to bulk job stream.')
      return
    }

    state.reconnectAttempts += 1
    clearReconnectTimer(state)
    state.reconnectTimer = setTimeout(() => {
      state.reconnectTimer = null
      if (state.refCount > 0 && state.token && !state.terminal) {
        ensureConnected(jobId, state.token)
      }
    }, 5000)
  }
}

/**
 * Subscribe to bulk job WebSocket events.
 * @param {string} token JWT
 * @param {string} jobId Bulk job id from POST response
 * @param {(data: object) => void} onEvent
 * @returns {() => void} unsubscribe
 */
export function subscribeBulkJob(token, jobId, onEvent) {
  if (!token || !jobId || typeof onEvent !== 'function') {
    return () => {}
  }

  const state = getJobState(jobId)
  state.listeners.add(onEvent)
  state.refCount += 1

  clearCloseTimer(state)
  clearReconnectTimer(state)
  ensureConnected(jobId, token)

  return () => {
    state.listeners.delete(onEvent)
    state.refCount = Math.max(0, state.refCount - 1)

    if (state.refCount > 0) return

    clearReconnectTimer(state)

    clearCloseTimer(state)
    state.closeTimer = setTimeout(() => {
      state.closeTimer = null
      if (state.refCount > 0) return
      closeSocket(state)
      state.token = null
      jobs.delete(jobId)
    }, 50)
  }
}
