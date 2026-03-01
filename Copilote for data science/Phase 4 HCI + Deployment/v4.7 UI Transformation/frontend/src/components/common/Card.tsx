// components/common/Card.tsx — Material elevation card
import React from 'react'

interface CardProps {
    children: React.ReactNode
    className?: string
    mode?: 'normal' | 'pro'
    elevation?: 0 | 1 | 2 | 3
    glow?: boolean
    onClick?: () => void
    padding?: 'none' | 'sm' | 'md' | 'lg'
}

const elevations = ['elevation-0', 'elevation-1', 'elevation-2', 'elevation-3']
const paddings: Record<string, string> = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-6' }

export default function Card({
    children, className = '', mode = 'normal', elevation = 1,
    glow = false, onClick, padding = 'md',
}: CardProps) {
    const radius = mode === 'pro' ? 'rounded-md' : 'rounded-xl'
    const glowClass = glow ? (mode === 'pro' ? 'animate-pulseGold' : 'animate-pulseGlow') : ''

    return (
        <div
            className={`
        bg-surface-1 border border-divider transition-material
        ${radius} ${elevations[elevation]} ${glowClass} ${paddings[padding]}
        ${onClick ? 'cursor-pointer hover:bg-surface-2 hover:border-surface-3' : ''}
        ${className}
      `}
            onClick={onClick}
        >
            {children}
        </div>
    )
}
