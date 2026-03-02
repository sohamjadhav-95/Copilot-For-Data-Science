// store/proStore.ts — Pro Mode state management (plan, execution, status polling)
import { create } from 'zustand'
import { proApi } from '../services/api'

interface DAGNode {
    node_id: string
    label: string
    operation: string
    node_type: string
    depends_on: string[]
    status?: string
    output_type?: string
    output_payload?: any
    metadata?: Record<string, any>
}

interface DAGPlan {
    plan_id: string
    user_goal: string
    nodes: DAGNode[]
    estimated_cost?: string
    complexity?: string
}

interface ProState {
    mode: 'idle' | 'classifying' | 'planning' | 'reviewing' | 'executing' | 'completed' | 'error'
    plan: DAGPlan | null
    executionResult: any | null
    nodeStatuses: Record<string, any>
    pollingId: ReturnType<typeof setInterval> | null
    error: string | null
    datasetProfile: any | null

    classify: (message: string, sessionId: number) => Promise<'simple' | 'complex'>
    generatePlan: (message: string, sessionId: number) => Promise<void>
    approvePlan: () => Promise<void>
    pollStatus: () => void
    stopPolling: () => void
    loadProfile: (sessionId: number) => Promise<void>
    reset: () => void
}

export const useProStore = create<ProState>((set, get) => ({
    mode: 'idle',
    plan: null,
    executionResult: null,
    nodeStatuses: {},
    pollingId: null,
    error: null,
    datasetProfile: null,

    classify: async (message, sessionId) => {
        set({ mode: 'classifying', error: null })
        try {
            const res = await proApi.classify(message, sessionId)
            const complexity = res.data.needs_pro ? 'complex' : 'simple'
            if (complexity === 'simple') set({ mode: 'idle' })
            return complexity as 'simple' | 'complex'
        } catch (err: any) {
            set({ mode: 'error', error: err.response?.data?.error || 'Classification failed' })
            return 'simple'
        }
    },

    generatePlan: async (message, sessionId) => {
        set({ mode: 'planning', error: null, plan: null })
        try {
            const res = await proApi.plan(message, sessionId)
            if (res.data.requires_confirmation) {
                set({ mode: 'error', error: res.data.warning })
                return
            }
            set({ mode: 'reviewing', plan: res.data })
        } catch (err: any) {
            set({ mode: 'error', error: err.response?.data?.error || 'Planning failed' })
        }
    },

    approvePlan: async () => {
        const { plan } = get()
        if (!plan) return

        set({ mode: 'executing', error: null })
        try {
            const res = await proApi.approve(plan.plan_id)
            set({ executionResult: res.data, mode: 'completed' })
        } catch (err: any) {
            set({ mode: 'error', error: err.response?.data?.error || 'Execution failed' })
        }
    },

    pollStatus: () => {
        const { plan, pollingId: existingId } = get()
        if (!plan || existingId) return

        const id = setInterval(async () => {
            try {
                const res = await proApi.status(plan.plan_id)
                const data = res.data

                set({ nodeStatuses: data.nodes || {} })

                if (data.status === 'completed' || data.status === 'failed' || data.status === 'partial') {
                    get().stopPolling()
                    set({ executionResult: data, mode: data.status === 'failed' ? 'error' : 'completed' })
                }
            } catch {
                // Ignore polling errors
            }
        }, 2000)

        set({ pollingId: id })
    },

    stopPolling: () => {
        const { pollingId } = get()
        if (pollingId) {
            clearInterval(pollingId)
            set({ pollingId: null })
        }
    },

    loadProfile: async (sessionId) => {
        try {
            const res = await proApi.profile(sessionId)
            set({ datasetProfile: res.data.profile })
        } catch {
            // Profile load is non-critical
        }
    },

    reset: () => {
        get().stopPolling()
        set({
            mode: 'idle',
            plan: null,
            executionResult: null,
            nodeStatuses: {},
            error: null,
        })
    },
}))
