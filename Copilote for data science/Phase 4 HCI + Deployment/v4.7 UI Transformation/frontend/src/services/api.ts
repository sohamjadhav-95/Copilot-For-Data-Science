// services/api.ts — Axios instance with auth interceptors
import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach Bearer token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Response interceptor — handle 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token')
            localStorage.removeItem('user')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)

export default api

// ═══════════════════════════════════════════════════════════════════
// AUTH API
// ═══════════════════════════════════════════════════════════════════

export const authApi = {
    login: (login_id: string, password: string) =>
        api.post('/login', { login_id, password }),
    register: (username: string, email: string, password: string) =>
        api.post('/register', { username, email, password }),
    logout: () => api.post('/logout'),
    me: () => api.get('/me'),
}

// ═══════════════════════════════════════════════════════════════════
// DATASET API
// ═══════════════════════════════════════════════════════════════════

export const datasetApi = {
    upload: (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        return api.post('/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
    },
    getSessions: () => api.get('/sessions'),
    getMessages: (sessionId: number) => api.get(`/sessions/${sessionId}/messages`),
    downloadModified: (sessionId: number) =>
        api.get(`/download-modified?session_id=${sessionId}`, { responseType: 'blob' }),
}

// ═══════════════════════════════════════════════════════════════════
// NORMAL MODE API
// ═══════════════════════════════════════════════════════════════════

export const normalApi = {
    chat: (message: string, session_id: number) =>
        api.post('/chat', { message, session_id }),
}

// ═══════════════════════════════════════════════════════════════════
// PRO MODE API
// ═══════════════════════════════════════════════════════════════════

export const proApi = {
    classify: (message: string, session_id: number) =>
        api.post('/pro/classify', { message, session_id }),
    plan: (message: string, session_id: number, size_override = false) =>
        api.post('/pro/plan', { message, session_id, size_override }),
    approve: (plan_id: string) =>
        api.post('/pro/approve', { plan_id }),
    status: (plan_id: string) =>
        api.get(`/pro/status/${plan_id}`),
    profile: (session_id: number) =>
        api.post('/pro/profile', { session_id }),
}

// ═══════════════════════════════════════════════════════════════════
// PROFILE API
// ═══════════════════════════════════════════════════════════════════

export const profileApi = {
    activities: () => api.get('/activities'),
    codeSnippets: () => api.get('/code-snippets'),
    codeSnippetDetail: (id: number) => api.get(`/code-snippets/${id}`),
    getProvider: () => api.get('/provider'),
    switchProvider: (provider: string) => api.post('/provider', { provider }),
}
