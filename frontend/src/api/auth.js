import client from './client'

export const authApi = {
  login: (password) => client.post('/auth/login', { password }),
  status: () => client.get('/auth/status'),
  verify: () => client.get('/auth/me'),
  register: (username, password) => client.post('/auth/register', { username, password }),
}
