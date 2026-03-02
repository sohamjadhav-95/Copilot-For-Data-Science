// layouts/ProLayout.tsx — Material: Top Bar + Left (280) + Workspace (fluid) + Meta (300)
import { useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useProStore } from '../store/proStore'
import { useSessionStore } from '../store/sessionStore'
import Badge from '../components/common/Badge'

interface ProLayoutProps {
    sidebar: React.ReactNode
    workspace: React.ReactNode
    metadata: React.ReactNode
    onAnalyze?: () => void
    prompt?: string
    onPromptChange?: (v: string) => void
}

export default function ProLayout({ sidebar, workspace, metadata, onAnalyze, prompt = '', onPromptChange }: ProLayoutProps) {
    const navigate = useNavigate()
    const { user, logout } = useAuthStore()
    const { mode } = useProStore()
    const { activeSession, uploadFile } = useSessionStore()
    const fileRef = useRef<HTMLInputElement>(null)

    const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]; if (file) await uploadFile(file)
    }, [uploadFile])

    const modeLabel: Record<string, string> = {
        idle: 'Ready', classifying: 'Classifying...', planning: 'Planning...',
        reviewing: 'Plan Review', executing: 'Executing...', completed: 'Completed', error: 'Error',
    }
    const isProd = mode === 'executing' || mode === 'planning' || mode === 'classifying'

    return (
        <div className="flex flex-col h-screen overflow-hidden" style={{ background: '#0B1220' }}>
            {/* ── Top Control Bar ── */}
            <header className="h-14 bg-surface-1 border-b border-divider elevation-3 flex items-center px-4 gap-3 flex-shrink-0 z-30">
                {/* Logo */}
                <div className="flex items-center gap-2.5 flex-shrink-0">
                    <div className="w-8 h-8 rounded-md flex items-center justify-center bg-gradient-to-br from-gold to-amber-600 text-base-bg text-caption font-bold">DS</div>
                    <div className="hidden md:block">
                        <div className="text-caption font-semibold text-text-primary leading-tight">Data Copilot</div>
                        <div className="text-[9px] font-bold tracking-widest text-gold leading-tight">PRO MODE</div>
                    </div>
                </div>

                <div className="w-px h-7 bg-divider" />

                {/* Dataset */}
                {activeSession && (
                    <div className="flex items-center gap-1.5 px-2 py-1 bg-surface-2 border border-divider rounded-md">
                        <span className="text-[10px] text-text-muted">📄</span>
                        <span className="text-[11px] text-text-secondary truncate max-w-[100px]">{activeSession.filename}</span>
                    </div>
                )}

                {/* Upload */}
                <input type="file" ref={fileRef} onChange={handleUpload} accept=".csv" className="hidden" />
                <button onClick={() => fileRef.current?.click()}
                    className="h-8 px-2.5 text-[11px] bg-surface-2 border border-divider rounded-md text-text-muted hover:text-text-primary transition-material cursor-pointer">
                    Upload
                </button>

                {/* Prompt Input */}
                <div className="flex-1 flex items-center gap-2 max-w-xl">
                    <input type="text" value={prompt} onChange={(e) => onPromptChange?.(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && onAnalyze?.()}
                        placeholder={activeSession ? 'Describe your analysis goal...' : 'Upload a dataset first'}
                        disabled={!activeSession || isProd}
                        className="flex-1 material-input material-input-pro h-9 text-[13px] rounded-md" />
                    <button onClick={onAnalyze}
                        disabled={!prompt?.trim() || !activeSession || isProd}
                        className="h-9 px-4 rounded-md bg-gold text-base-bg text-caption font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gold-hover transition-material cursor-pointer elevation-1">
                        ⚡ Analyze
                    </button>
                </div>

                {/* Status */}
                <Badge variant={mode === 'error' ? 'error' : mode === 'completed' ? 'success' : mode === 'idle' ? 'neutral' : 'gold'} size="sm" dot>
                    {modeLabel[mode] || mode}
                </Badge>

                <div className="w-px h-7 bg-divider" />

                {/* Mode switch */}
                <button onClick={() => navigate('/normal')}
                    className="h-8 px-2.5 text-[11px] bg-accent/10 border border-accent/20 text-accent rounded-md hover:bg-accent/20 transition-material cursor-pointer">
                    ○ Normal
                </button>

                {/* User */}
                <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="w-7 h-7 rounded-full bg-gold/20 flex items-center justify-center text-[11px] font-bold text-gold">
                        {user?.username?.[0]?.toUpperCase()}
                    </div>
                    <button onClick={() => { logout(); navigate('/login') }}
                        className="text-[11px] text-text-muted hover:text-error transition-material cursor-pointer hidden lg:block">
                        Logout
                    </button>
                </div>
            </header>

            {/* ── Main Body ── */}
            <div className="flex flex-1 overflow-hidden">
                {/* Left Panel */}
                <aside className="w-[280px] border-r border-divider bg-surface-1 overflow-y-auto flex-shrink-0">
                    {sidebar}
                </aside>

                {/* Center Workspace */}
                <main className="flex-1 overflow-hidden">{workspace}</main>

                {/* Right Meta Panel */}
                <aside className="w-[300px] border-l border-divider bg-surface-1 overflow-hidden flex-shrink-0">
                    {metadata}
                </aside>
            </div>
        </div>
    )
}
