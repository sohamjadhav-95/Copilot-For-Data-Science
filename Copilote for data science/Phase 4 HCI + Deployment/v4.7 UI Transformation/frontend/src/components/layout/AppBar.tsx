// components/layout/AppBar.tsx — Material top app bar (64px)
import React, { useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/authStore'
import { useSessionStore } from '../../store/sessionStore'

interface AppBarProps {
    mode: 'normal' | 'pro'
}

export default function AppBar({ mode }: AppBarProps) {
    const navigate = useNavigate()
    const { user, logout } = useAuthStore()
    const { activeSession, uploadFile } = useSessionStore()
    const fileRef = useRef<HTMLInputElement>(null)

    const isPro = mode === 'pro'
    const accentBg = isPro ? 'bg-gold/10 text-gold border-gold/20' : 'bg-accent/10 text-accent border-accent/20'

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) await uploadFile(file)
    }

    return (
        <header className="h-16 bg-surface-1 border-b border-divider elevation-2 flex items-center px-4 gap-4 flex-shrink-0 z-30 relative">
            {/* Logo */}
            <div className="flex items-center gap-3 flex-shrink-0">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm ${isPro ? 'bg-gradient-to-br from-gold to-amber-600 text-base-bg' : 'bg-gradient-to-br from-accent to-blue-400 text-white'}`}>
                    DS
                </div>
                <div className="hidden sm:block">
                    <div className="text-caption font-semibold text-text-primary leading-tight">Data Copilot</div>
                    <div className="text-overline text-text-muted leading-tight">{isPro ? 'PRO' : 'ENTERPRISE'}</div>
                </div>
            </div>

            {/* Divider */}
            <div className="w-px h-8 bg-divider" />

            {/* Dataset Indicator */}
            {activeSession && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-divider rounded-lg">
                    <svg className="w-3.5 h-3.5 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="text-caption text-text-secondary truncate max-w-[120px]">{activeSession.filename}</span>
                </div>
            )}

            {/* Upload */}
            <input type="file" ref={fileRef} onChange={handleUpload} accept=".csv" className="hidden" />
            <button
                onClick={() => fileRef.current?.click()}
                className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-surface-2 border border-divider text-caption text-text-secondary hover:text-text-primary hover:bg-surface-3 transition-material cursor-pointer"
            >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                Upload
            </button>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Mode Switch */}
            <button
                onClick={() => navigate(isPro ? '/normal' : '/pro')}
                className={`flex items-center gap-2 h-8 px-3 rounded-lg border text-caption font-medium transition-material cursor-pointer ${accentBg}`}
            >
                {isPro ? '○ Normal' : '⚡ Pro Mode'}
            </button>

            {/* Settings */}
            <button
                onClick={() => navigate('/settings')}
                className="p-2 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition-material cursor-pointer"
            >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            </button>

            {/* User Avatar */}
            <div className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-caption font-bold ${isPro ? 'bg-gold/20 text-gold' : 'bg-accent/20 text-accent'}`}>
                    {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <button
                    onClick={() => { logout(); navigate('/login') }}
                    className="text-caption text-text-muted hover:text-error transition-material cursor-pointer hidden sm:block"
                >
                    Logout
                </button>
            </div>
        </header>
    )
}
