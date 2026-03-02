// components/normal/ResultPanel.tsx — Material results display
import { useMemo } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import DataTable from '../data/DataTable'
import InteractiveChart from '../data/InteractiveChart'
import Card from '../common/Card'

export default function ResultPanel() {
    const { messages, dataset } = useSessionStore()

    const lastResult = useMemo(() => {
        const res = messages.filter((m) => m.role === 'assistant' && m.result_type)
        return res[res.length - 1] || null
    }, [messages])

    const parsed = useMemo(() => {
        if (!lastResult?.result_data || !lastResult.result_type) return null
        if (lastResult.result_type === 'dataframe' || lastResult.result_type === 'modify') {
            try { return JSON.parse(lastResult.result_data) } catch { return null }
        }
        return lastResult.result_data
    }, [lastResult])

    return (
        <div className="h-full overflow-y-auto p-4 space-y-4">
            {/* Dataset card */}
            {dataset && (
                <Card elevation={1} className="animate-fadeIn">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
                            <svg className="w-4 h-4 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        </div>
                        <div>
                            <h4 className="text-body-sm font-semibold text-text-primary">{dataset.filename}</h4>
                            <p className="text-caption text-text-muted">{dataset.rows.toLocaleString()} rows × {dataset.columns} cols</p>
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-center">
                        <Stat label="Numeric" value={dataset.numeric_count} color="text-accent" />
                        <Stat label="Missing" value={dataset.missing} color="text-warning" />
                        <Stat label="Columns" value={dataset.columns} color="text-success" />
                    </div>
                </Card>
            )}

            {/* Latest result */}
            {lastResult && (
                <div className="animate-fadeIn">
                    {lastResult.result_title && (
                        <h3 className="text-body-sm font-semibold text-text-primary mb-3">{lastResult.result_title}</h3>
                    )}
                    {(lastResult.result_type === 'dataframe' || lastResult.result_type === 'modify') && parsed && (
                        <DataTable data={parsed} title={lastResult.result_title || undefined} />
                    )}
                    {lastResult.result_type === 'chart' && (
                        <InteractiveChart base64Image={parsed as string} title={lastResult.result_title || undefined} />
                    )}
                    {lastResult.result_type === 'text' && (
                        <Card><p className="text-body-sm text-text-primary whitespace-pre-wrap">{lastResult.result_data}</p></Card>
                    )}
                </div>
            )}

            {/* Empty state */}
            {!lastResult && !dataset && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                    <div className="w-16 h-16 rounded-2xl bg-surface-2 flex items-center justify-center mb-4 opacity-40">
                        <svg className="w-8 h-8 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    </div>
                    <h3 className="text-title text-text-primary mb-2">No Results Yet</h3>
                    <p className="text-body-sm text-text-muted max-w-xs">Upload a dataset and ask questions to see interactive tables and charts</p>
                </div>
            )}
        </div>
    )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div className="bg-base-bg rounded-lg p-2.5">
            <div className={`text-headline font-bold ${color}`}>{value}</div>
            <div className="text-[10px] text-text-muted mt-0.5">{label}</div>
        </div>
    )
}
