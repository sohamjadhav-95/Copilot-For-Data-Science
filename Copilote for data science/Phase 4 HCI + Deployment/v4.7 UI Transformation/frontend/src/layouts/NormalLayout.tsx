// layouts/NormalLayout.tsx — Material: AppBar (64px) + Sidebar (260px) + Chat (40%) | Results (60%)
import { useEffect } from 'react'
import { useSessionStore } from '../store/sessionStore'
import AppBar from '../components/layout/AppBar'
import Sidebar, { SessionList } from '../components/layout/Sidebar'
import Card from '../components/common/Card'

interface NormalLayoutProps {
    chatPanel: React.ReactNode
    resultPanel: React.ReactNode
}

export default function NormalLayout({ chatPanel, resultPanel }: NormalLayoutProps) {
    const { dataset, loadSessions } = useSessionStore()

    useEffect(() => { loadSessions() }, [loadSessions])

    const sidebarSections = [
        {
            id: 'sessions', title: 'Sessions', defaultOpen: true,
            content: <SessionList mode="normal" />,
        },
        ...(dataset ? [{
            id: 'dataset', title: 'Dataset Info', defaultOpen: true,
            content: (
                <div className="space-y-2 text-caption">
                    <div className="flex justify-between"><span className="text-text-muted">File</span><span className="text-text-primary font-mono truncate ml-2">{dataset.filename}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">Rows</span><span className="text-text-primary font-mono">{dataset.rows.toLocaleString()}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">Columns</span><span className="text-text-primary font-mono">{dataset.columns}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">Missing</span><span className="text-warning font-mono">{dataset.missing}</span></div>
                    <div className="flex justify-between"><span className="text-text-muted">Numeric</span><span className="text-accent font-mono">{dataset.numeric_count}</span></div>
                </div>
            ),
        }] : []),
    ]

    return (
        <div className="flex flex-col h-screen bg-base-bg overflow-hidden">
            <AppBar mode="normal" />
            <div className="flex flex-1 overflow-hidden">
                <Sidebar sections={sidebarSections} width={260} mode="normal" />
                <main className="flex-1 flex overflow-hidden">
                    <div className="w-[40%] border-r border-divider">{chatPanel}</div>
                    <div className="w-[60%]">{resultPanel}</div>
                </main>
            </div>
        </div>
    )
}
