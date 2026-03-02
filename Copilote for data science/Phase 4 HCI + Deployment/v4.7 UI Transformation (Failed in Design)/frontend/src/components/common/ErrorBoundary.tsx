// components/common/ErrorBoundary.tsx
import React, { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { hasError: boolean; error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
    state: State = { hasError: false, error: null }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error }
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error('[ErrorBoundary]', error, info)
    }

    render() {
        if (this.state.hasError) {
            return this.props.fallback || (
                <div className="flex items-center justify-center min-h-[200px] p-8">
                    <div className="text-center">
                        <div className="text-4xl mb-4">⚠️</div>
                        <h3 className="text-lg font-semibold text-normal-text mb-2">Something went wrong</h3>
                        <p className="text-normal-text-secondary text-sm mb-4">
                            {this.state.error?.message || 'An unexpected error occurred'}
                        </p>
                        <button
                            onClick={() => this.setState({ hasError: false, error: null })}
                            className="px-4 py-2 bg-normal-accent text-white rounded-lg text-sm hover:bg-normal-accent-light transition-colors cursor-pointer"
                        >
                            Try Again
                        </button>
                    </div>
                </div>
            )
        }
        return this.props.children
    }
}
