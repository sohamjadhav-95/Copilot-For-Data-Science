// store/authStore.ts — Authentication state management
import { create } from 'zustand'
import { authApi } from '../services/api'

interface User {
    id: number
    username: string
    email: string
    created_at: string
}

interface AuthState {
    user: User | null
    token: string | null
    isAuthenticated: boolean
    isLoading: boolean
    error: string | null

    login: (loginId: string, password: string) => Promise<boolean>
    register: (username: string, email: string, password: string) => Promise<boolean>
    logout: () => void
    loadUser: () => Promise<void>
    clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token'),
    isAuthenticated: !!localStorage.getItem('token'),
    isLoading: false,
    error: null,

    login: async (loginId, password) => {
        set({ isLoading: true, error: null })
        try {
            const res = await authApi.login(loginId, password)
            const { user, token } = res.data
            localStorage.setItem('token', token)
            localStorage.setItem('user', JSON.stringify(user))
            set({ user, token, isAuthenticated: true, isLoading: false })
            return true
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Login failed', isLoading: false })
            return false
        }
    },

    register: async (username, email, password) => {
        set({ isLoading: true, error: null })
        try {
            const res = await authApi.register(username, email, password)
            const { user, token } = res.data
            localStorage.setItem('token', token)
            localStorage.setItem('user', JSON.stringify(user))
            set({ user, token, isAuthenticated: true, isLoading: false })
            return true
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Registration failed', isLoading: false })
            return false
        }
    },

    logout: () => {
        authApi.logout().catch(() => { })
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        set({ user: null, token: null, isAuthenticated: false })
    },

    loadUser: async () => {
        try {
            const res = await authApi.me()
            set({ user: res.data.user, isAuthenticated: true })
        } catch {
            localStorage.removeItem('token')
            localStorage.removeItem('user')
            set({ user: null, token: null, isAuthenticated: false })
        }
    },

    clearError: () => set({ error: null }),
}))
