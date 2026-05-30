import { create } from 'zustand'
import { authApi } from '../api/auth'

export const useAuthStore = create((set, get) => ({
  token: localStorage.getItem('token') || null,
  user: null,
  isAuthenticated: !!localStorage.getItem('token'),

  login: async (password) => {
    try {
      const response = await authApi.login(password)
      const { access_token } = response.data
      localStorage.setItem('token', access_token)
      set({ token: access_token, isAuthenticated: true })
      // Fetch user info after login
      const userRes = await authApi.verify()
      set({ user: userRes.data })
      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Login failed',
      }
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null, isAuthenticated: false })
  },

  checkAuth: async () => {
    const token = get().token
    if (!token) {
      set({ isAuthenticated: false, user: null })
      return false
    }
    try {
      const response = await authApi.verify()
      set({ user: response.data, isAuthenticated: true })
      return true
    } catch {
      localStorage.removeItem('token')
      set({ token: null, user: null, isAuthenticated: false })
      return false
    }
  },
}))
