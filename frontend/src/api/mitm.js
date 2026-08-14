import client from './client'

export const mitmApi = {
  // Config
  getConfig: () => client.get('/mitm/config'),
  updateConfig: (data) => client.patch('/mitm/config', data),

  // Server control
  startMitm: () => client.post('/mitm/start'),
  stopMitm: () => client.post('/mitm/stop'),
  generateCert: () => client.post('/mitm/generate-cert'),
  downloadCert: () => client.get('/mitm/cert', { responseType: 'blob' }),
  getStatus: () => client.get('/mitm/status'),

  // Logs
  getLogs: (params = {}) => client.get('/mitm/logs', { params }),
  clearLogs: () => client.delete('/mitm/logs'),
}
