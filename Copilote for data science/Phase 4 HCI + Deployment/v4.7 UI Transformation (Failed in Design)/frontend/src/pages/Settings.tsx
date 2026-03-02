// pages/Settings.tsx — Material settings page
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { profileApi } from '../services/api'
import { useAuthStore } from '../store/authStore'
import Button from '../components/common/Button'
import Card from '../components/common/Card'
import Badge from '../components/common/Badge'
import AppBar from '../components/layout/AppBar'

export default function Settings() {
    const navigate = useNavigate()
    const { user } = useAuthStore()
    const [provider, setProvider] = useState('')
    const [providers, setProviders] = useState<string[]>([])
    const [switching, setSwitching] = useState(false)

    useEffect(() => {
        profileApi.getProvider().then((r) => {
            setProvider(r.data.active_provider); setProviders(r.data.available_providers)
        }).catch(() => { })
    }, [])

    const handleSwitch = async (p: string) => {
        setSwitching(true)
        try { const r = await profileApi.switchProvider(p); setProvider(r.data.active_provider) } catch { }
        setSwitching(false)
    }

    return (
        <div className="flex flex-col h-screen bg-base-bg overflow-hidden">
            <AppBar mode="normal" />
            <main className="flex-1 overflow-y-auto">
                <div className="max-w-2xl mx-auto p-6 space-y-6">
                    <h2 className="text-headline text-text-primary">Settings</h2>

                    {/* Account */}
                    <Card elevation={1}>
                        <h3 className="text-title text-text-primary mb-4">Account</h3>
                        <div className="space-y-3">
                            <Row label="Username" value={user?.username} />
                            <Row label="Email" value={user?.email} />
                            <Row label="Member Since" value={user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'} />
                        </div>
                    </Card>

                    {/* AI Provider */}
                    <Card elevation={1}>
                        <h3 className="text-title text-text-primary mb-4">AI Provider</h3>
                        <div className="space-y-2">
                            {providers.map((p) => (
                                <div key={p} className={`flex items-center justify-between px-4 py-3 rounded-lg border transition-material
                  ${p === provider ? 'bg-accent/10 border-accent/20' : 'border-divider hover:bg-surface-2'}`}>
                                    <div className="flex items-center gap-3">
                                        <span className="text-body-sm text-text-primary capitalize">{p}</span>
                                        {p === provider && <Badge variant="success" size="sm" dot>Active</Badge>}
                                    </div>
                                    {p !== provider && (
                                        <Button size="sm" variant="secondary" loading={switching} onClick={() => handleSwitch(p)}>Switch</Button>
                                    )}
                                </div>
                            ))}
                        </div>
                    </Card>
                </div>
            </main>
        </div>
    )
}

function Row({ label, value }: { label: string; value: any }) {
    return (
        <div className="flex justify-between text-body-sm">
            <span className="text-text-muted">{label}</span>
            <span className="text-text-primary">{value || '—'}</span>
        </div>
    )
}
