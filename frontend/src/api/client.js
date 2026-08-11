import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const client = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Share identical in-flight GET requests.
 * React StrictMode (dev) mounts effects twice; without this every
 * page fires duplicate GETs with the same URL+params.
 */
const inflightGets = new Map()

function getDedupeKey(config) {
  const method = (config.method || 'get').toLowerCase()
  if (method !== 'get') return null
  if (config.dedupe === false) return null
  const params = config.params
    ? JSON.stringify(config.params, Object.keys(config.params).sort())
    : ''
  return `${method}|${config.url || ''}|${params}`
}

client.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    const key = getDedupeKey(config)
    if (!key) return config

    const existing = inflightGets.get(key)
    if (existing) {
      // Reuse the in-flight response instead of opening a second XHR.
      config.adapter = () =>
        existing.then((response) => ({
          data: response.data,
          status: response.status,
          statusText: response.statusText,
          headers: response.headers,
          config,
          request: response.request,
        }))
      return config
    }

    let resolve
    let reject
    const deferred = new Promise((res, rej) => {
      resolve = res
      reject = rej
    })
    inflightGets.set(key, deferred)
    config.__dedupeKey = key
    config.__dedupeResolve = resolve
    config.__dedupeReject = reject
    return config
  },
  (error) => Promise.reject(error)
)

function settleDedupe(config, error, response) {
  if (!config?.__dedupeResolve) return
  const key = config.__dedupeKey
  if (error) config.__dedupeReject(error)
  else config.__dedupeResolve(response)
  if (key) inflightGets.delete(key)
}

// Response interceptor - settle dedupe + handle 401
client.interceptors.response.use(
  (response) => {
    settleDedupe(response.config, null, response)
    return response
  },
  (error) => {
    if (error.config) settleDedupe(error.config, error, null)
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
