// components/pro/PlanApproval.tsx — Material plan review card
import Button from '../common/Button'
import Badge from '../common/Badge'
import Card from '../common/Card'

interface PlanNode {
    node_id: string; label: string; operation: string; node_type: string; depends_on: string[]
}

interface PlanApprovalProps {
    planId: string; userGoal: string; nodes: PlanNode[]
    estimatedCost?: string; onApprove: () => void; onCancel: () => void; isApproving: boolean
}

export default function PlanApproval({ planId, userGoal, nodes, estimatedCost, onApprove, onCancel, isApproving }: PlanApprovalProps) {
    return (
        <div className="space-y-4 animate-fadeIn">
            {/* Header */}
            <Card mode="pro" elevation={2} padding="lg">
                <div className="flex items-start justify-between mb-2">
                    <div>
                        <h3 className="text-title text-text-primary mb-1">Execution Plan</h3>
                        <p className="text-body-sm text-text-secondary">{userGoal}</p>
                    </div>
                    <Badge variant="gold" size="md">{nodes.length} steps</Badge>
                </div>
                {estimatedCost && <p className="text-caption text-text-muted mt-2">Estimated: {estimatedCost}</p>}
            </Card>

            {/* Step list */}
            <div className="space-y-1.5">
                {nodes.map((node, i) => (
                    <div key={node.node_id}
                        className="flex items-center gap-3 px-4 py-3 bg-surface-1 border border-divider rounded-md elevation-1">
                        <div className="w-6 h-6 rounded flex items-center justify-center bg-gold-surface text-gold text-caption font-bold flex-shrink-0">
                            {i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="text-body-sm font-medium text-text-primary">{node.label}</span>
                                <Badge variant="neutral" size="sm">{node.node_type}</Badge>
                            </div>
                            <p className="text-[11px] text-text-muted mt-0.5">{node.operation}</p>
                        </div>
                        {node.depends_on.length > 0 && (
                            <span className="text-[10px] text-text-muted flex-shrink-0">← {node.depends_on.join(', ')}</span>
                        )}
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
                <Button variant="ghost" onClick={onCancel} disabled={isApproving}>Cancel</Button>
                <Button variant="gold" onClick={onApprove} loading={isApproving}
                    icon={<span>⚡</span>}>Approve & Execute</Button>
            </div>
        </div>
    )
}
