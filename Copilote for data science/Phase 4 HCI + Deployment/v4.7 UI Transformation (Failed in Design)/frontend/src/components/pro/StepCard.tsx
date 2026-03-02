// components/pro/StepCard.tsx — Material step result card with expand/collapse
import { useState, useRef, useEffect, useMemo } from 'react'
import Badge from '../common/Badge'
import DataTable from '../data/DataTable'
import InteractiveChart from '../data/InteractiveChart'

interface StepCardProps {
    nodeId: string
    index: number
    label: string
    operation: string
    status: string
    durationMs?: number
    modelUsed?: string
    retryCount?: number
    outputType?: string
    outputPayload?: any
    error?: string
    isNew?: boolean
}

const statusConfig: Record<string, { icon: string; badge: 'success' | 'error' | 'warning' | 'info' | 'neutral' }> = {
    pending: { icon: '○', badge: 'neutral' },
    running: { icon: '◉', badge: 'info' },
    success: { icon: '✓', badge: 'success' },
    failed: { icon: '✗', badge: 'error' },
    skipped: { icon: '⊘', badge: 'neutral' },
    retrying: { icon: '↻', badge: 'warning' },
}

export default function StepCard({
    nodeId, index, label, operation, status, durationMs, modelUsed,
    retryCount, outputType, outputPayload, error, isNew,
}: StepCardProps) {
    const [expanded, setExpanded] = useState(false)
    const cardRef = useRef<HTMLDivElement>(null)
    const cfg = statusConfig[status] || statusConfig.pending
    const isActive = status === 'running'

    // Auto-scroll into view when step completes
    useEffect(() => {
        if (isNew && (status === 'success' || status === 'failed')) {
            cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }
    }, [status, isNew])

    const parsedOutput = useMemo(() => {
        if (!outputPayload) return null
        if (typeof outputPayload === 'string') {
            try { return JSON.parse(outputPayload) } catch { return outputPayload }
        }
        return outputPayload
    }, [outputPayload])

    const hasOutput = outputPayload || error

    return (
        <div
            ref={cardRef}
            className={`
        bg-surface-1 border border-divider rounded-md overflow-hidden elevation-1
        transition-material
        ${isActive ? 'border-info/40 animate-pulseGlow' : ''}
        ${isNew ? 'animate-fadeIn' : ''}
      `}
        >
            {/* Header */}
            <button
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2 transition-material cursor-pointer"
                onClick={() => hasOutput && setExpanded(!expanded)}
            >
                {/* Step number */}
                <div className={`
          w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-caption font-bold
          ${status === 'success' ? 'bg-success-surface text-success' :
                        status === 'failed' ? 'bg-error-surface text-error' :
                            status === 'running' ? 'bg-info-surface text-info' :
                                'bg-surface-2 text-text-muted'
                    }
        `}>
                    {status === 'success' ? '✓' : status === 'failed' ? '✗' : index + 1}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0 text-left">
                    <div className="flex items-center gap-2">
                        <span className="text-body-sm font-medium text-text-primary truncate">{label}</span>
                        <Badge variant={cfg.badge} size="sm" dot>{status}</Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-[11px] text-text-muted">{operation}</span>
                        {durationMs !== undefined && (
                            <span className="text-[11px] text-text-muted">⏱ {(durationMs / 1000).toFixed(1)}s</span>
                        )}
                        {modelUsed && <span className="text-[11px] text-text-muted">🤖 {modelUsed}</span>}
                        {(retryCount || 0) > 0 && <span className="text-[11px] text-warning">↻ {retryCount}</span>}
                    </div>
                </div>

                {/* Expand toggle */}
                {hasOutput && (
                    <svg className={`w-4 h-4 text-text-muted transition-transform duration-150 flex-shrink-0 ${expanded ? 'rotate-180' : ''}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                )}
            </button>

            {/* Expanded Output */}
            {expanded && hasOutput && (
                <div className="border-t border-divider p-4 bg-base-bg animate-fadeIn space-y-3">
                    {/* Error */}
                    {error && (
                        <div className="p-3 rounded-md bg-error-surface border border-error/20">
                            <p className="text-mono text-error text-[12px]">{error}</p>
                        </div>
                    )}

                    {/* DataFrame output */}
                    {outputType === 'dataframe' && parsedOutput && (
                        <DataTable data={parsedOutput} title={`${label} — Output`} compact />
                    )}

                    {/* Artifact / Chart */}
                    {outputType === 'artifact' && typeof parsedOutput === 'string' && parsedOutput.length > 100 && (
                        <InteractiveChart base64Image={parsedOutput} title={`${label} — Chart`} mode="pro" />
                    )}

                    {/* Scalar */}
                    {outputType === 'scalar' && (
                        <div className="p-3 rounded-md bg-surface-2">
                            <p className="text-mono text-text-primary">{String(parsedOutput)}</p>
                        </div>
                    )}

                    {/* Dict / JSON */}
                    {outputType === 'dict' && parsedOutput && typeof parsedOutput === 'object' && (
                        <pre className="p-3 rounded-md bg-surface-2 text-mono text-[11px] text-text-secondary overflow-x-auto max-h-60 overflow-y-auto">
                            {JSON.stringify(parsedOutput, null, 2)}
                        </pre>
                    )}

                    {/* Console output */}
                    {outputType === 'text' && parsedOutput && (
                        <div className="p-3 rounded-md bg-surface-2">
                            <p className="text-body-sm text-text-primary whitespace-pre-wrap">{String(parsedOutput)}</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
