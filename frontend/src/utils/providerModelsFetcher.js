// Fetch and cache suggested models for providers that expose a public models API
// Fetches via backend proxy to avoid CORS issues

import client from '../api/client'

const CACHE_TTL_MS = 10 * 60 * 1000 // 10 minutes
const cache = new Map() // key: fetcher.url -> { data, expiresAt }
const inflight = new Map() // key: fetcher.url -> Promise

/**
 * Fetch suggested models for a provider using its modelsFetcher config.
 * Results are cached in-memory for CACHE_TTL_MS.
 * @param {{ url: string, type: string }} fetcher
 * @returns {Promise<Array<{ id: string, name: string, contextLength?: number }>>}
 */
export async function fetchSuggestedModels(fetcher) {
  if (!fetcher?.url || !fetcher?.type) return []

  const cached = cache.get(fetcher.url)
  if (cached && Date.now() < cached.expiresAt) return cached.data

  const existing = inflight.get(fetcher.url)
  if (existing) return existing

  const pending = (async () => {
    try {
      const res = await client.get('/providers/suggested-models', {
        params: { url: fetcher.url, type: fetcher.type },
      })
      const data = res.data?.data ?? []
      cache.set(fetcher.url, { data, expiresAt: Date.now() + CACHE_TTL_MS })
      return data
    } catch {
      return []
    } finally {
      inflight.delete(fetcher.url)
    }
  })()

  inflight.set(fetcher.url, pending)
  return pending
}
