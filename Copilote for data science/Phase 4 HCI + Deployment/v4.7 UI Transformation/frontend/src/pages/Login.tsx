// pages/Login.tsx — Material Design 420px centered card
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import Button from '../components/common/Button'

export default function Login() {
    const navigate = useNavigate()
    const { login, isLoading, error, clearError } = useAuthStore()
    const [loginId, setLoginId] = useState('')
    const [password, setPassword] = useState('')

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        const ok = await login(loginId, password)
        if (ok) navigate('/normal')
    }

    return (
        <div className="min-h-screen bg-base-bg flex items-center justify-center p-4">
            {/* Gradient background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/3 left-1/3 w-[500px] h-[500px] bg-accent/4 rounded-full blur-3xl" />
                <div className="absolute bottom-1/3 right-1/3 w-[400px] h-[400px] bg-info/3 rounded-full blur-3xl" />
            </div>

            <div className="relative w-full max-w-[420px] animate-fadeInScale">
                {/* Logo */}
                <div className="text-center mb-8">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent to-blue-400 flex items-center justify-center mx-auto mb-4 elevation-2">
                        <span className="text-white text-xl font-bold">DS</span>
                    </div>
                    <h1 className="text-display text-text-primary">Data Science Copilot</h1>
                    <p className="text-body-sm text-text-muted mt-1">Enterprise Analytics Platform</p>
                </div>

                {/* Card */}
                <form onSubmit={handleSubmit} className="bg-surface-1 border border-divider rounded-2xl p-6 elevation-3">
                    <h2 className="text-title text-text-primary mb-6">Sign In</h2>

                    {error && (
                        <div className="mb-4 p-3 rounded-lg bg-error-surface border border-error/20 text-error text-body-sm animate-fadeIn">
                            {error}
                            <button onClick={clearError} className="float-right text-error/60 hover:text-error cursor-pointer">×</button>
                        </div>
                    )}

                    <div className="space-y-4">
                        <div>
                            <label className="block text-caption text-text-muted mb-1.5">Username or Email</label>
                            <input type="text" value={loginId} onChange={(e) => setLoginId(e.target.value)}
                                className="w-full material-input" placeholder="Enter username or email" required />
                        </div>
                        <div>
                            <label className="block text-caption text-text-muted mb-1.5">Password</label>
                            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                                className="w-full material-input" placeholder="Enter password" required />
                        </div>
                    </div>

                    <Button type="submit" loading={isLoading} className="w-full mt-6">Sign In</Button>

                    <p className="text-center text-body-sm text-text-muted mt-4">
                        Don't have an account?{' '}
                        <Link to="/register" className="text-accent hover:underline">Register</Link>
                    </p>
                </form>
            </div>
        </div>
    )
}
