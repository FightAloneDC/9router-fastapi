import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
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

function getDefaultAdapter(config) {
  return axios.getAdapter(config.adapter || 'http')
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
      config.adapter = () => existing
      return config
    }

    const defaultAdapter = getDefaultAdapter(config)
    const tracked = defaultAdapter(config).finally(() => {
      inflightGets.delete(key)
    })
    inflightGets.set(key, tracked)
    config.adapter = () => tracked
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default client
