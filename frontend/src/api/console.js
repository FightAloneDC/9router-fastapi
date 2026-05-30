import client from './client'

export const consoleApi = {
  getLogs: (limit = 100) => client.get(`/console/logs?limit=${limit}`),
}
