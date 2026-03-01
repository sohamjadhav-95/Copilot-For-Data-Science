// components/layout/Sidebar.tsx — Material sidebar with collapsible sections
import React, { useState } from 'react'
import { useSessionStore } from '../../store/sessionStore'

interface SidebarSection {
    id: string
    title: string
    content: React.ReactNode
    defaultOpen?: boolean
}

interface SidebarProps {
    sections: SidebarSection[]
    width?: number
    mode?: 'normal' | 'pro'
}

function CollapsibleSection({ title, children, defaultOpen = true, mode = 'normal' }: {
    title: string; children: React.ReactNode; defaultOpen?: boolean; mode?: string
}) {
    const [open, setOpen] = useState(defaultOpen)
    return (
        <div className="border-b border-divider last:border-b-0">
            <button
                className="w-full flex items-center justify-between px-4 py-3 text-overline text-text-muted hover:text-text-secondary transition-material cursor-pointer"
                onClick={() => setOpen(!open)}
            >
                {title}
                <svg className={`w-3.5 h-3.5 transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>
            {open && <div className="px-4 pb-3 animate-fadeIn">{children}</div>}
        </div>
    )
}

export default function Sidebar({ sections, width = 260, mode = 'normal' }: SidebarProps) {
    return (
        <aside
            className="h-full bg-surface-1 border-r border-divider overflow-y-auto flex-shrink-0"
            style={{ width }}
        >
            {sections.map((s) => (
                <CollapsibleSection key={s.id} title={s.title} defaultOpen={s.defaultOpen ?? true} mode={mode}>
                    {s.content}
                </CollapsibleSection>
            ))}
        </aside>
    )
}

// ── Session List (for sidebar use) ──
export function SessionList({ mode = 'normal' }: { mode?: 'normal' | 'pro' }) {
    const { sessions, activeSession, selectSession } = useSessionStore()
    const accentClasses = mode === 'pro'
        ? 'bg-gold/10 text-gold border-gold/20'
        : 'bg-accent/10 text-accent border-accent/20'

    return (
        <div className="space-y-1">
            {sessions.length === 0 && (
                <p className="text-caption text-text-muted py-2">No sessions yet</p>
            )}
            {sessions.map((s) => (
                <button
                    key={s.id}
                    onClick={() => selectSession(s)}
                    className={`
            w-full text-left px-3 py-2 rounded-lg text-caption transition-material cursor-pointer
            ${activeSession?.id === s.id
                            ? `${accentClasses} border`
                            : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
                        }
          `}
                >
                    <div className="truncate font-medium">{s.filename || s.title}</div>
                    <div className="text-[10px] text-text-muted mt-0.5">{s.message_count || 0} messages</div>
                </button>
            ))}
        </div>
    )
}
