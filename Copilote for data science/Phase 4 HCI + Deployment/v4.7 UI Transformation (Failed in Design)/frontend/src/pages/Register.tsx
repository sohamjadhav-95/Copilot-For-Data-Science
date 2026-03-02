// pages/Register.tsx — Material registration
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import Button from '../components/common/Button'

export default function Register() {
    const navigate = useNavigate()
    const { register, isLoading, error, clearError } = useAuthStore()
    const [username, setUsername] = useState('')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirm, setConfirm] = useState('')
    const [localErr, setLocalErr] = useState('')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault(); setLocalErr('')
        if (password !== confirm) { setLocalErr('Passwords do not match'); return }
        const ok = await register(username, email, password)
        if (ok) navigate('/normal')
    }

    const err = localErr || error

    return (
        <div className="min-h-screen bg-base-bg flex items-center justify-center p-4">
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/3 left-1/3 w-[500px] h-[500px] bg-accent/4 rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-1/3 w-[400px] h-[400px] bg-info/3 rounded-full blur-3xl" />
            </div>

            <div className="relative w-full max-w-[420px] animate-fadeInScale">
                <div className="text-center mb-8">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent to-blue-400 flex items-center justify-center mx-auto mb-4 elevation-2">
                        <span className="text-white text-xl font-bold">DS</span>
                    </div>
                    <h1 className="text-display text-text-primary">Create Account</h1>
                    <p className="text-body-sm text-text-muted mt-1">Join the Enterprise Platform</p>
                </div>

                <form onSubmit={handleSubmit} className="bg-surface-1 border border-divider rounded-2xl p-6 elevation-3">
                    <h2 className="text-title text-text-primary mb-6">Register</h2>

                    {err && (
                        <div className="mb-4 p-3 rounded-lg bg-error-surface border border-error/20 text-error text-body-sm animate-fadeIn">
                            {err}
                            <button onClick={() => { clearError(); setLocalErr('') }} className="float-right text-error/60 hover:text-error cursor-pointer">×</button>
                        </div>
                    )}

                    <div className="space-y-4">
                        <div><label className="block text-caption text-text-muted mb-1.5">Username</label>
                            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                                className="w-full material-input" placeholder="Choose a username" required /></div>
                        <div><label className="block text-caption text-text-muted mb-1.5">Email</label>
                            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                                className="w-full material-input" placeholder="Enter email" required /></div>
                        <div><label className="block text-caption text-text-muted mb-1.5">Password</label>
                            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                                className="w-full material-input" placeholder="Min 6 characters" required minLength={6} /></div>
                        <div><label className="block text-caption text-text-muted mb-1.5">Confirm Password</label>
                            <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                                className="w-full material-input" placeholder="Repeat password" required minLength={6} /></div>
                    </div>

                    <Button type="submit" loading={isLoading} className="w-full mt-6">Create Account</Button>

                    <p className="text-center text-body-sm text-text-muted mt-4">
                        Already have an account? <Link to="/login" className="text-accent hover:underline">Sign In</Link>
                    </p>
                </form>
            </div>
        </div>
    )
}
