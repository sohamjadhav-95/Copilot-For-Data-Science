// store/sessionStore.ts — Session and dataset state management
import { create } from 'zustand'
import { datasetApi, normalApi } from '../services/api'

interface DatasetInfo {
    filename: string
    rows: number
    columns: number
    column_names: string[]
    dtypes: Record<string, string>
    missing: number
    numeric_count: number
    session_id: number
}

interface MessageData {
    id: number
    role: 'user' | 'assistant'
    content: string
    result_type?: string | null
    result_data?: string | null
    result_title?: string | null
    created_at: string
}

interface Session {
    id: number
    filename: string | null
    title: string
    created_at: string
    message_count: number
}

interface SessionState {
    sessions: Session[]
    activeSession: Session | null
    dataset: DatasetInfo | null
    messages: MessageData[]
    isLoading: boolean
    isSending: boolean
    error: string | null

    loadSessions: () => Promise<void>
    selectSession: (session: Session) => Promise<void>
    uploadFile: (file: File) => Promise<void>
    sendMessage: (message: string) => Promise<void>
    clearError: () => void
}

export const useSessionStore = create<SessionState>((set, get) => ({
    sessions: [],
    activeSession: null,
    dataset: null,
    messages: [],
    isLoading: false,
    isSending: false,
    error: null,

    loadSessions: async () => {
        set({ isLoading: true })
        try {
            const res = await datasetApi.getSessions()
            set({ sessions: res.data.sessions, isLoading: false })
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Failed to load sessions', isLoading: false })
        }
    },

    selectSession: async (session) => {
        set({ activeSession: session, isLoading: true, messages: [], dataset: null })
        try {
            const res = await datasetApi.getMessages(session.id)
            set({
                messages: res.data.messages,
                dataset: res.data.dataset,
                isLoading: false,
            })
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Failed to load session', isLoading: false })
        }
    },

    uploadFile: async (file) => {
        set({ isLoading: true, error: null })
        try {
            const res = await datasetApi.upload(file)
            const { dataset } = res.data
            const newSession: Session = {
                id: dataset.session_id,
                filename: dataset.filename,
                title: `Chat: ${dataset.filename}`,
                created_at: new Date().toISOString(),
                message_count: 0,
            }
            set((state) => ({
                sessions: [newSession, ...state.sessions],
                activeSession: newSession,
                dataset,
                messages: [],
                isLoading: false,
            }))
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Upload failed', isLoading: false })
        }
    },

    sendMessage: async (message) => {
        const { activeSession } = get()
        if (!activeSession) return

        set({ isSending: true, error: null })
        try {
            const res = await normalApi.chat(message, activeSession.id)
            const { user_msg, assistant_msg } = res.data
            set((state) => ({
                messages: [...state.messages, user_msg, assistant_msg],
                isSending: false,
            }))
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Message failed', isSending: false })
        }
    },

    clearError: () => set({ error: null }),
}))
