// components/pro/ExecutionTracker.tsx — Material progress tracker
import Badge from '../common/Badge'

interface TrackerNode {
    node_id: string; label: string; operation: string; status: string
    duration_ms?: number; model_used?: string; retry_count?: number
}

interface ExecutionTrackerProps { nodes: TrackerNode[]; className?: string }

export default function ExecutionTracker({ nodes, className = '' }: ExecutionTrackerProps) {
    const total = nodes.length
    const done = nodes.filter((n) => n.status === 'success').length
    const failed = nodes.filter((n) => n.status === 'failed').length
    const pct = total > 0 ? (done / total) * 100 : 0

    return (
        <div className={`space-y-3 ${className}`}>
            {/* Progress bar */}
            <div>
                <div className="flex items-center justify-between mb-1.5">
                    <span className="text-overline text-text-muted">Progress</span>
                    <span className="text-caption text-text-secondary">{done}/{total} {failed > 0 && `(${failed} failed)`}</span>
                </div>
                <div className="w-full h-1.5 bg-surface-2 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${pct}%`, background: failed > 0 ? 'linear-gradient(90deg, #10B981, #EF4444)' : '#10B981' }} />
                </div>
            </div>

            {/* Step list */}
            <div className="space-y-1">
                {nodes.map((n) => {
                    const isActive = n.status === 'running'
                    const isDone = n.status === 'success'
                    const isFailed = n.status === 'failed'

                    return (
                        <div key={n.node_id} className={`flex items-center gap-3 px-3 py-2 rounded-md transition-material
              ${isActive ? 'bg-info-surface/50 border border-info/20' : 'hover:bg-surface-2'}
            `}>
                            <div className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold flex-shrink-0
                ${isDone ? 'bg-success-surface text-success' :
                                    isFailed ? 'bg-error-surface text-error' :
                                        isActive ? 'bg-info-surface text-info' :
                                            'bg-surface-2 text-text-muted'}
              `}>
                                {isDone ? '✓' : isFailed ? '✗' : isActive ? '◉' : '○'}
                            </div>
                            <div className="flex-1 min-w-0">
                                <span className="text-caption text-text-primary truncate block">{n.label}</span>
                            </div>
                            {n.duration_ms !== undefined && (
                                <span className="text-[10px] text-text-muted flex-shrink-0">{(n.duration_ms / 1000).toFixed(1)}s</span>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
