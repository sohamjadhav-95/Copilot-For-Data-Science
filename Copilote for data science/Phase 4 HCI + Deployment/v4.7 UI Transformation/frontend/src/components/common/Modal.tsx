// components/common/Modal.tsx — Material Design dialog
import React, { useEffect } from 'react'

interface ModalProps {
    isOpen: boolean
    onClose: () => void
    title?: string
    children: React.ReactNode
    size?: 'sm' | 'md' | 'lg'
}

const sizeMap: Record<string, string> = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl' }

export default function Modal({ isOpen, onClose, title, children, size = 'md' }: ModalProps) {
    useEffect(() => {
        const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
        if (isOpen) { document.addEventListener('keydown', esc); document.body.style.overflow = 'hidden' }
        return () => { document.removeEventListener('keydown', esc); document.body.style.overflow = '' }
    }, [isOpen, onClose])

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Scrim */}
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

            {/* Dialog */}
            <div className={`
        relative ${sizeMap[size]} w-full mx-4
        bg-surface-1 border border-divider rounded-2xl elevation-4
        animate-fadeInScale
      `}>
                {title && (
                    <div className="flex items-center justify-between px-6 py-4 border-b border-divider">
                        <h3 className="text-title text-text-primary">{title}</h3>
                        <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-material p-1 rounded-lg hover:bg-surface-2 cursor-pointer">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                )}
                <div className="p-6">{children}</div>
            </div>
        </div>
    )
}
