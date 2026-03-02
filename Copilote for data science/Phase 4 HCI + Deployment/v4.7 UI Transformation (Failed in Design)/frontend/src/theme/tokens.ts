// theme/tokens.ts — Material Design token system
export const colors = {
    base: {
        bg: '#0B1220',
        surface1: '#111827',
        surface2: '#1F2937',
        surface3: '#374151',
        divider: '#1E293B',
    },
    text: {
        primary: '#F3F4F6',
        secondary: '#9CA3AF',
        muted: '#6B7280',
        disabled: '#4B5563',
    },
    normal: {
        accent: '#2563EB',
        accentHover: '#1D4ED8',
        accentMuted: '#1E40AF',
        accentSurface: '#172554',
    },
    pro: {
        gold: '#D4AF37',
        goldHover: '#C9A22E',
        goldMuted: '#92702A',
        goldSurface: '#1C1709',
        navy: '#0F172A',
    },
    semantic: {
        success: '#10B981',
        successSurface: '#064E3B',
        error: '#EF4444',
        errorSurface: '#7F1D1D',
        warning: '#F59E0B',
        warningSurface: '#78350F',
        info: '#3B82F6',
        infoSurface: '#1E3A5F',
    },
} as const

// Material elevation shadow presets  
export const elevation = {
    0: 'none',
    1: '0 1px 3px rgba(0,0,0,0.24), 0 1px 2px rgba(0,0,0,0.36)',
    2: '0 3px 6px rgba(0,0,0,0.28), 0 3px 6px rgba(0,0,0,0.34)',
    3: '0 10px 20px rgba(0,0,0,0.30), 0 6px 6px rgba(0,0,0,0.32)',
    4: '0 14px 28px rgba(0,0,0,0.35), 0 10px 10px rgba(0,0,0,0.30)',
} as const

// 8px spacing grid
export const spacing = {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
} as const

export type ThemeMode = 'normal' | 'pro'
