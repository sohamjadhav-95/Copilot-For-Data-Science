// pages/ProWorkspace.tsx — Pro Workflow Studio
import { useState, useEffect, useMemo } from 'react'
import { useSessionStore } from '../store/sessionStore'
import { useProStore } from '../store/proStore'
import ProLayout from '../layouts/ProLayout'
import DAGViewer from '../components/pro/DAGViewer'
import ExecutionTracker from '../components/pro/ExecutionTracker'
import StepCard from '../components/pro/StepCard'
import PlanApproval from '../components/pro/PlanApproval'
import MetadataPanel from '../components/pro/MetadataPanel'
import { SessionList } from '../components/layout/Sidebar'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import ErrorBoundary from '../components/common/ErrorBoundary'

export default function ProWorkspace() {
    const { sessions, activeSession, selectSession, loadSessions, dataset } = useSessionStore()
    const pro = useProStore()
    const [prompt, setPrompt] = useState('')
    const [prevStatuses, setPrevStatuses] = useState<Record<string, string>>({})

    useEffect(() => { loadSessions() }, [loadSessions])
    useEffect(() => { if (activeSession) pro.loadProfile(activeSession.id) }, [activeSession])

    // Track newly completed steps for scroll-into-view
    const newlyCompleted = useMemo(() => {
        const newIds = new Set<string>()
        Object.entries(pro.nodeStatuses).forEach(([id, ns]: [string, any]) => {
            if ((ns.status === 'success' || ns.status === 'failed') && prevStatuses[id] !== ns.status) {
                newIds.add(id)
            }
        })
        return newIds
    }, [pro.nodeStatuses])

    useEffect(() => {
        const s: Record<string, string> = {}
        Object.entries(pro.nodeStatuses).forEach(([id, ns]: [string, any]) => { s[id] = ns.status })
        setPrevStatuses(s)
    }, [pro.nodeStatuses])

    const handleAnalyze = async () => {
        if (!prompt.trim() || !activeSession) return
        const complexity = await pro.classify(prompt, activeSession.id)
        if (complexity === 'complex') await pro.generatePlan(prompt, activeSession.id)
    }

    // ── Sidebar ──
    const sidebarContent = (
        <div className="p-0">
            {/* Sessions */}
            <div className="border-b border-divider">
                <div className="px-4 py-3 text-overline text-text-muted">Sessions</div>
                <div className="px-4 pb-3">
                    <SessionList mode="pro" />
                </div>
            </div>

            {/* Dataset Profile */}
            {pro.datasetProfile && (
                <div className="border-b border-divider">
                    <div className="px-4 py-3 text-overline text-text-muted">Dataset Profile</div>
                    <div className="px-4 pb-3 space-y-1.5 text-caption">
                        <Row label="Shape" value={`${pro.datasetProfile.shape?.[0]} × ${pro.datasetProfile.shape?.[1]}`} />
                        <Row label="Missing" value={pro.datasetProfile.missing_cells || 0} />
                    </div>
                </div>
            )}

            {/* Execution Tracker (compact in sidebar) */}
            {(pro.mode === 'executing' || pro.mode === 'completed') && pro.plan && (
                <div className="border-b border-divider">
                    <div className="px-4 py-3 text-overline text-text-muted">Execution</div>
                    <div className="px-4 pb-3">
                        <ExecutionTracker nodes={pro.plan.nodes.map((n) => ({
                            ...n, status: pro.nodeStatuses[n.node_id]?.status || 'pending',
                            duration_ms: pro.nodeStatuses[n.node_id]?.duration_ms,
                            model_used: pro.nodeStatuses[n.node_id]?.model_used,
                            retry_count: pro.nodeStatuses[n.node_id]?.retry_count,
                        }))} />
                    </div>
                </div>
            )}

            {/* Plan Summary */}
            {pro.plan && (
                <div>
                    <div className="px-4 py-3 text-overline text-text-muted">Plan</div>
                    <div className="px-4 pb-3 space-y-1">
                        {pro.plan.nodes.map((n: any, i: number) => (
                            <div key={n.node_id} className="flex items-center gap-2 text-caption">
                                <span className="text-gold font-bold w-4 text-right">{i + 1}</span>
                                <span className="text-text-secondary truncate">{n.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )

    // ── Main Workspace ──
    const workspaceContent = (
        <div className="h-full overflow-y-auto p-6 space-y-6">
            {/* Error */}
            {pro.error && (
                <div className="max-w-3xl mx-auto p-4 rounded-md bg-error-surface border border-error/20 text-error text-body-sm animate-fadeIn">
                    {pro.error}
                    <button onClick={pro.reset} className="ml-3 underline text-error/60 hover:text-error cursor-pointer">Reset</button>
                </div>
            )}

            {/* Plan Review */}
            {pro.mode === 'reviewing' && pro.plan && (
                <div className="max-w-3xl mx-auto space-y-4 animate-fadeIn">
                    <ErrorBoundary>
                        <DAGViewer nodes={pro.plan.nodes} height={360} />
                    </ErrorBoundary>
                    <PlanApproval planId={pro.plan.plan_id} userGoal={pro.plan.user_goal}
                        nodes={pro.plan.nodes} estimatedCost={pro.plan.estimated_cost}
                        onApprove={() => pro.approvePlan()} onCancel={pro.reset} isApproving={false} />
                </div>
            )}

            {/* Execution + Step Results */}
            {(pro.mode === 'executing' || pro.mode === 'completed') && pro.plan && (
                <div className="max-w-3xl mx-auto space-y-4 animate-fadeIn">
                    <ErrorBoundary>
                        <DAGViewer nodes={pro.plan.nodes} nodeStatuses={pro.nodeStatuses} height={320} />
                    </ErrorBoundary>

                    {/* Step Cards */}
                    <div className="space-y-2">
                        <h3 className="text-overline text-text-muted">Step Results</h3>
                        {pro.plan.nodes.map((node: any, i: number) => {
                            const ns = pro.nodeStatuses[node.node_id] || {}
                            return (
                                <StepCard key={node.node_id}
                                    nodeId={node.node_id} index={i} label={node.label} operation={node.operation}
                                    status={ns.status || 'pending'} durationMs={ns.duration_ms}
                                    modelUsed={ns.model_used} retryCount={ns.retry_count}
                                    outputType={ns.output_type} outputPayload={ns.output_payload}
                                    error={ns.error} isNew={newlyCompleted.has(node.node_id)} />
                            )
                        })}
                    </div>

                    {/* Final Summary */}
                    {pro.executionResult?.summary && (
                        <Card mode="pro" elevation={2} className="border-gold/20">
                            <h3 className="text-body-sm font-semibold text-gold mb-2">Analysis Summary</h3>
                            <p className="text-body-sm text-text-primary whitespace-pre-wrap leading-relaxed">{pro.executionResult.summary}</p>
                        </Card>
                    )}
                </div>
            )}

            {/* Idle state */}
            {pro.mode === 'idle' && !pro.plan && (
                <div className="flex flex-col items-center justify-center text-center py-24">
                    <div className="w-20 h-20 rounded-2xl bg-surface-2 flex items-center justify-center mb-6 opacity-30">
                        <span className="text-4xl">⚡</span>
                    </div>
                    <h3 className="text-headline text-text-primary mb-2">Pro Workspace</h3>
                    <p className="text-body-sm text-text-muted max-w-md">
                        {activeSession
                            ? 'Describe a complex analysis goal in the bar above. The engine will create a multi-step DAG plan for your approval.'
                            : 'Upload a CSV dataset to begin a Pro analysis session.'}
                    </p>
                    <div className="flex flex-wrap gap-2 mt-6 justify-center">
                        <Badge variant="neutral" size="md">Multi-step DAG</Badge>
                        <Badge variant="neutral" size="md">Live Results</Badge>
                        <Badge variant="neutral" size="md">Auto Replanning</Badge>
                    </div>
                </div>
            )}
        </div>
    )

    return (
        <ProLayout
            sidebar={sidebarContent}
            workspace={<ErrorBoundary>{workspaceContent}</ErrorBoundary>}
            metadata={<MetadataPanel plan={pro.plan} executionResult={pro.executionResult}
                nodeStatuses={pro.nodeStatuses} datasetProfile={pro.datasetProfile} />}
            prompt={prompt} onPromptChange={setPrompt} onAnalyze={handleAnalyze}
        />
    )
}

function Row({ label, value }: { label: string; value: any }) {
    return (
        <div className="flex justify-between">
            <span className="text-text-muted">{label}</span>
            <span className="text-text-primary font-mono">{value}</span>
        </div>
    )
}
