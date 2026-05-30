import client from './client'

export const oauthApi = {
  // Generate auth URL + PKCE data for authorization code flows
  authorize: (provider, redirectUri = 'http://localhost:8080/callback') =>
    client.get(`/oauth/${provider}/authorize`, { params: { redirect_uri: redirectUri } }),

  // Exchange authorization code for tokens and save connection
  exchange: (provider, data) =>
    client.post(`/oauth/${provider}/exchange`, data),

  // Request device code for device_code flow providers
  deviceCode: (provider, params = {}) =>
    client.get(`/oauth/${provider}/device-code`, { params }),

  // Poll for device code token
  poll: (provider, data) =>
    client.post(`/oauth/${provider}/poll`, data),

  // Auto-import cursor tokens
  autoImportCursor: () =>
    client.get('/oauth/cursor/auto-import'),

  // Import token (cursor)
  importToken: (provider, data) =>
    client.post(`/oauth/${provider}/import-token`, data),

  // Codex proxy: start local proxy server on port 1455
  startCodexProxy: (params) =>
    client.get('/oauth/codex/start-proxy', { params }),

  // Codex proxy: poll for completion status
  pollCodexStatus: (state) =>
    client.get('/oauth/codex/poll-status', { params: { state } }),

  // Codex proxy: stop the proxy server
  stopCodexProxy: () =>
    client.get('/oauth/codex/stop-proxy'),
}
