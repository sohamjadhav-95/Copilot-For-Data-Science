// components/common/Button.tsx — Material Design button
import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'gold'
    size?: 'sm' | 'md' | 'lg'
    loading?: boolean
    icon?: React.ReactNode
    children: React.ReactNode
}

const variants: Record<string, string> = {
    primary: 'bg-accent text-white hover:bg-accent-hover elevation-1 hover:elevation-2',
    secondary: 'bg-surface-2 text-text-primary border border-divider hover:bg-surface-3',
    ghost: 'bg-transparent text-text-secondary hover:bg-surface-2 hover:text-text-primary',
    danger: 'bg-error text-white hover:brightness-110 elevation-1',
    gold: 'bg-gold text-base-bg font-semibold hover:bg-gold-hover elevation-1 hover:elevation-2',
}

const sizes: Record<string, string> = {
    sm: 'h-8 px-3 text-caption gap-1.5',
    md: 'h-10 px-4 text-body-sm gap-2',
    lg: 'h-12 px-6 text-body gap-2.5',
}

export default function Button({
    variant = 'primary', size = 'md', loading = false,
    icon, children, className = '', disabled, ...props
}: ButtonProps) {
    return (
        <button
            className={`
        inline-flex items-center justify-center rounded-lg font-medium
        transition-material cursor-pointer select-none
        disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none
        active:scale-[0.98]
        ${variants[variant]} ${sizes[size]} ${className}
      `}
            disabled={disabled || loading}
            {...props}
        >
            {loading ? (
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
            ) : icon ? (
                <span className="flex-shrink-0">{icon}</span>
            ) : null}
            {children}
        </button>
    )
}
