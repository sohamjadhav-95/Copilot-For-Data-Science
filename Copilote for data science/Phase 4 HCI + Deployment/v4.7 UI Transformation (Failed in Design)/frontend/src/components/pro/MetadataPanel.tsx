// components/pro/MetadataPanel.tsx — Material sticky right panel (300px)
import Card from '../common/Card'
import Badge from '../common/Badge'

interface MetadataPanelProps {
    plan?: any
    executionResult?: any
    nodeStatuses?: Record<string, any>
    datasetProfile?: any
}

export default function MetadataPanel({ plan, executionResult, nodeStatuses = {}, datasetProfile }: MetadataPanelProps) {
    const totalDuration = Object.values(nodeStatuses).reduce((a: number, n: any) => a + (n?.duration_ms || 0), 0)
    const models = [...new Set(Object.values(nodeStatuses).map((n: any) => n?.model_used).filter(Boolean))]
    const retries = Object.values(nodeStatuses).reduce((a: number, n: any) => a + (n?.retry_count || 0), 0)

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4">
            <h3 className="text-overline text-text-muted">Metadata</h3>

            {/* Execution Stats */}
            {Object.keys(nodeStatuses).length > 0 && (
                <Card mode="pro" elevation={1} padding="sm">
                    <div className="space-y-2.5">
                        <Row label="Duration" value={`${(totalDuration / 1000).toFixed(1)}s`} mono />
                        <Row label="Retries" value={<Badge variant={retries > 0 ? 'warning' : 'success'} size="sm">{retries}</Badge>} />
                        {models.length > 0 && (
                            <div>
                                <span className="text-[10px] text-text-muted block mb-1">Models</span>
                                <div className="flex flex-wrap gap-1">
                                    {models.map((m) => <Badge key={m as string} variant="neutral" size="sm">{m as string}</Badge>)}
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Dataset Profile */}
            {datasetProfile && (
                <Card mode="pro" elevation={1} padding="sm">
                    <h4 className="text-overline text-text-muted mb-2">Dataset</h4>
                    <div className="space-y-2">
                        <Row label="Rows" value={datasetProfile.shape?.[0]?.toLocaleString()} mono />
                        <Row label="Columns" value={datasetProfile.shape?.[1]} mono />
                        {datasetProfile.warnings?.length > 0 && (
                            <div className="pt-2 border-t border-divider">
                                <span className="text-[10px] text-text-muted block mb-1">⚠ Warnings</span>
                                {datasetProfile.warnings.slice(0, 3).map((w: string, i: number) => (
                                    <p key={i} className="text-[10px] text-warning leading-relaxed">{w}</p>
                                ))}
                            </div>
                        )}
                    </div>
                </Card>
            )}

            {/* Plan */}
            {plan && (
                <Card mode="pro" elevation={1} padding="sm">
                    <h4 className="text-overline text-text-muted mb-2">Plan</h4>
                    <p className="text-caption text-text-secondary mb-2 leading-relaxed">{plan.user_goal}</p>
                    <div className="flex gap-2">
                        <Badge variant="gold" size="sm">{plan.nodes?.length || 0} nodes</Badge>
                        <Badge variant="neutral" size="sm">{plan.plan_id?.substring(0, 8)}</Badge>
                    </div>
                </Card>
            )}

            {/* Status */}
            {executionResult?.status && (
                <Card mode="pro" elevation={1} padding="sm">
                    <h4 className="text-overline text-text-muted mb-2">Status</h4>
                    <Badge variant={
                        executionResult.status === 'completed' ? 'success' :
                            executionResult.status === 'failed' ? 'error' : 'warning'
                    } size="md" dot>{executionResult.status}</Badge>
                </Card>
            )}
        </div>
    )
}

function Row({ label, value, mono }: { label: string; value: any; mono?: boolean }) {
    return (
        <div className="flex items-center justify-between">
            <span className="text-[11px] text-text-muted">{label}</span>
            {typeof value === 'string' || typeof value === 'number' ? (
                <span className={`text-caption text-text-primary ${mono ? 'font-mono' : ''}`}>{value}</span>
            ) : value}
        </div>
    )
}
