// components/pro/StepResult.tsx — Expandable result per DAG node
import { useState, useMemo } from 'react'
import DataTable from '../data/DataTable'
import InteractiveChart from '../data/InteractiveChart'
import Badge from '../common/Badge'

interface StepResultProps {
    nodeId: string
    label: string
    status: string
    outputType?: string
    outputPayload?: any
    metadata?: Record<string, any>
}

export default function StepResult({ nodeId, label, status, outputType, outputPayload, metadata }: StepResultProps) {
    const [expanded, setExpanded] = useState(false)

    const parsedData = useMemo(() => {
        if (!outputPayload) return null
        if (typeof outputPayload === 'string') {
            try { return JSON.parse(outputPayload) } catch { return outputPayload }
        }
        return outputPayload
    }, [outputPayload])

    if (!outputPayload && status !== 'failed') return null

    return (
        <div className="border border-pro-border rounded-xl overflow-hidden bg-pro-surface">
            {/* Header */}
            <button
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-pro-surface-hover transition-colors cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <div className="flex items-center gap-3">
                    <span className={`text-xs transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
                    <span className="text-sm font-medium text-pro-text">{label}</span>
                    <Badge variant={status === 'success' ? 'success' : status === 'failed' ? 'error' : 'neutral'}>
                        {status}
                    </Badge>
                    {outputType && (
                        <span className="text-xs text-pro-text-secondary">({outputType})</span>
                    )}
                </div>
                {metadata?.duration_ms && (
                    <span className="text-xs text-pro-text-secondary">
                        ⏱ {(metadata.duration_ms / 1000).toFixed(1)}s
                    </span>
                )}
            </button>

            {/* Expanded content */}
            {expanded && (
                <div className="border-t border-pro-border p-4 animate-fadeIn">
                    {outputType === 'dataframe' && parsedData && (
                        <DataTable data={parsedData} title={`${label} Output`} />
                    )}

                    {outputType === 'artifact' && typeof parsedData === 'string' && parsedData.length > 100 && (
                        <InteractiveChart base64Image={parsedData} title={`${label} Chart`} />
                    )}

                    {outputType === 'scalar' && (
                        <div className="bg-pro-bg rounded-lg p-4">
                            <p className="text-sm text-pro-text font-mono">{String(parsedData)}</p>
                        </div>
                    )}

                    {outputType === 'dict' && parsedData && (
                        <pre className="bg-pro-bg rounded-lg p-4 text-xs text-pro-text-secondary font-mono overflow-x-auto">
                            {JSON.stringify(parsedData, null, 2)}
                        </pre>
                    )}

                    {status === 'failed' && metadata?.error && (
                        <div className="bg-error-bg rounded-lg p-4 border border-error/30">
                            <p className="text-sm text-error font-mono">{metadata.error}</p>
                        </div>
                    )}

                    {/* Metadata */}
                    {metadata && (
                        <div className="flex flex-wrap gap-3 mt-3 pt-3 border-t border-pro-border">
                            {metadata.model_used && (
                                <span className="text-xs text-pro-text-secondary">🤖 {metadata.model_used}</span>
                            )}
                            {metadata.retry_count > 0 && (
                                <span className="text-xs text-warning">↻ {metadata.retry_count} retries</span>
                            )}
                            {metadata.token_estimate && (
                                <span className="text-xs text-pro-text-secondary">🔤 ~{metadata.token_estimate} tokens</span>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
