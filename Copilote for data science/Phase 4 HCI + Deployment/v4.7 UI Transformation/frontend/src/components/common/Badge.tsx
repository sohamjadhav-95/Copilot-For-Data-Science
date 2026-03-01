// components/common/Badge.tsx — Material chip-style badge
import React from 'react'

interface BadgeProps {
    children: React.ReactNode
    variant?: 'success' | 'error' | 'warning' | 'info' | 'neutral' | 'gold'
    size?: 'sm' | 'md'
    dot?: boolean
    className?: string
}

const variants: Record<string, string> = {
    success: 'bg-success-surface text-success border-success/20',
    error: 'bg-error-surface text-error border-error/20',
    warning: 'bg-warning-surface text-warning border-warning/20',
    info: 'bg-info-surface text-info border-info/20',
    neutral: 'bg-surface-2 text-text-secondary border-divider',
    gold: 'bg-gold-surface text-gold border-gold/20',
}

export default function Badge({ children, variant = 'neutral', size = 'sm', dot = false, className = '' }: BadgeProps) {
    return (
        <span className={`
      inline-flex items-center gap-1.5 border font-medium
      ${size === 'sm' ? 'px-2 py-0.5 text-[10px] rounded' : 'px-2.5 py-1 text-[11px] rounded-md'}
      ${variants[variant]} ${className}
    `}>
            {dot && <span className={`w-1.5 h-1.5 rounded-full bg-current`} />}
            {children}
        </span>
    )
}
