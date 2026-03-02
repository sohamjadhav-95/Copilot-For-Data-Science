// components/pro/DAGViewer.tsx — React Flow DAG visualization (Material)
import { useMemo } from 'react'
import { ReactFlow, Background, Controls, type Node, type Edge, Position } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

interface DAGNode {
    node_id: string
    label: string
    operation: string
    node_type: string
    depends_on: string[]
    status?: string
}

interface DAGViewerProps {
    nodes: DAGNode[]
    nodeStatuses?: Record<string, any>
    className?: string
    height?: number
}

const statusBorder: Record<string, string> = {
    pending: '#374151', running: '#3B82F6', success: '#10B981',
    failed: '#EF4444', skipped: '#374151', retrying: '#F59E0B',
}

export default function DAGViewer({ nodes: dagNodes, nodeStatuses = {}, className = '', height = 400 }: DAGViewerProps) {
    const { nodes, edges } = useMemo(() => {
        const flowNodes: Node[] = dagNodes.map((n, i) => {
            const st = n.status || nodeStatuses[n.node_id]?.status || 'pending'
            return {
                id: n.node_id,
                position: { x: 250, y: i * 110 },
                data: {
                    label: (
                        <div className="text-left">
                            <div className="text-[11px] font-semibold text-text-primary mb-0.5">{n.label}</div>
                            <div className="text-[10px] text-text-muted">{n.operation}</div>
                            {nodeStatuses[n.node_id]?.duration_ms && (
                                <div className="text-[10px] text-text-muted mt-1">⏱ {(nodeStatuses[n.node_id].duration_ms / 1000).toFixed(1)}s</div>
                            )}
                        </div>
                    ),
                },
                sourcePosition: Position.Bottom,
                targetPosition: Position.Top,
                style: {
                    background: '#111827', border: `2px solid ${statusBorder[st]}`,
                    borderRadius: '6px', padding: '10px 14px', minWidth: '200px',
                    boxShadow: st === 'running' ? `0 0 16px ${statusBorder.running}40` : '0 1px 3px rgba(0,0,0,0.24)',
                },
            }
        })

        const flowEdges: Edge[] = dagNodes.flatMap((n) =>
            n.depends_on.map((dep) => ({
                id: `${dep}-${n.node_id}`, source: dep, target: n.node_id,
                animated: nodeStatuses[n.node_id]?.status === 'running',
                style: { stroke: '#1E293B', strokeWidth: 2 },
            }))
        )
        return { nodes: flowNodes, edges: flowEdges }
    }, [dagNodes, nodeStatuses])

    return (
        <div className={`rounded-md border border-divider overflow-hidden bg-base-bg elevation-1 ${className}`} style={{ height }}>
            <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
                <Background color="#1F2937" gap={20} />
                <Controls />
            </ReactFlow>
        </div>
    )
}
