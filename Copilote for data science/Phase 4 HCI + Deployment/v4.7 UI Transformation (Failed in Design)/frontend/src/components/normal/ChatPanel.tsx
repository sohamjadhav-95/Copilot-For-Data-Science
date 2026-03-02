// components/normal/ChatPanel.tsx — Material chat with proper spacing
import { useState, useRef, useEffect } from 'react'
import { useSessionStore } from '../../store/sessionStore'
import Button from '../common/Button'

export default function ChatPanel() {
    const { messages, isSending, sendMessage, activeSession } = useSessionStore()
    const [input, setInput] = useState('')
    const endRef = useRef<HTMLDivElement>(null)

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

    const handleSend = async () => {
        const msg = input.trim()
        if (!msg || isSending) return
        setInput('')
        await sendMessage(msg)
    }

    return (
        <div className="flex flex-col h-full">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {!activeSession && (
                    <div className="flex items-center justify-center h-full">
                        <p className="text-body-sm text-text-muted text-center">Upload a CSV dataset to start</p>
                    </div>
                )}

                {messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}>
                        <div className={`
              max-w-[75%] px-4 py-2.5 text-body-sm leading-relaxed
              ${msg.role === 'user'
                                ? 'bg-accent text-white rounded-2xl rounded-br-md elevation-1'
                                : 'bg-surface-1 border border-divider text-text-primary rounded-2xl rounded-bl-md elevation-1'
                            }
            `}>
                            <p className="whitespace-pre-wrap">{msg.content}</p>
                            {msg.result_type && (
                                <div className="mt-2 pt-2 border-t border-white/10 flex items-center gap-1.5">
                                    <span className="text-[10px] opacity-70">
                                        {msg.result_type === 'chart' ? '📈' : msg.result_type === 'dataframe' ? '📋' : '📝'} Result →
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {isSending && (
                    <div className="flex justify-start animate-fadeIn">
                        <div className="bg-surface-1 border border-divider rounded-2xl rounded-bl-md px-4 py-3 elevation-1">
                            <div className="flex items-center gap-2 text-body-sm text-text-muted">
                                <div className="flex gap-1">
                                    <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <span className="w-1.5 h-1.5 bg-accent rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                                Analyzing...
                            </div>
                        </div>
                    </div>
                )}
                <div ref={endRef} />
            </div>

            {/* Input */}
            <div className="border-t border-divider p-4 bg-surface-1">
                <div className="flex gap-3">
                    <textarea value={input} onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                        placeholder={activeSession ? 'Ask about your data...' : 'Upload a dataset first'}
                        disabled={!activeSession} rows={1}
                        className="flex-1 material-input rounded-xl resize-none"
                        style={{ minHeight: '42px', maxHeight: '120px' }}
                        onInput={(e) => {
                            const t = e.target as HTMLTextAreaElement; t.style.height = 'auto'
                            t.style.height = Math.min(t.scrollHeight, 120) + 'px'
                        }} />
                    <Button onClick={handleSend} disabled={!input.trim() || isSending || !activeSession}
                        loading={isSending} className="self-end"
                        icon={
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                        }>Send</Button>
                </div>
            </div>
        </div>
    )
}
