import { useState, useRef, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import UploadPanel from './components/UploadPanel'
import ChatMessage from './components/ChatMessage'
import ChatInput from './components/ChatInput'
import { askQuestion, clearHistory } from './lib/api'

// Persist session ID across page reloads
function getSessionId() {
    let id = localStorage.getItem('policypal_session')
    if (!id) {
        id = uuidv4()
        localStorage.setItem('policypal_session', id)
    }
    return id
}

export default function App() {
    const [tenant, setTenant] = useState('hr')
    const [messages, setMessages] = useState([])   // {role, content, sources}
    const [streaming, setStreaming] = useState(false)
    const [error, setError] = useState(null)
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const sessionId = useRef(getSessionId())
    const bottomRef = useRef()

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSend = async (question) => {
        setError(null)
        setStreaming(true)
        const userMsg = { role: 'user', content: question, sources: [] }
        const botMsg = { role: 'assistant', content: '', sources: [], streaming: true }
        setMessages((prev) => [...prev, userMsg, botMsg])

        await askQuestion({
            question,
            sessionId: sessionId.current,
            tenant,
            topK: 5,
            onSources: (sources) => {
                setMessages((prev) => {
                    const next = [...prev]
                    next[next.length - 1] = { ...next[next.length - 1], sources }
                    return next
                })
            },
            onToken: (token) => {
                setMessages((prev) => {
                    const next = [...prev]
                    next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + token }
                    return next
                })
            },
            onDone: () => {
                setStreaming(false)
                setMessages((prev) => {
                    const next = [...prev]
                    next[next.length - 1] = { ...next[next.length - 1], streaming: false }
                    return next
                })
            },
            onError: (e) => {
                setStreaming(false)
                setError(e.message)
            },
        })
    }

    const handleClear = async () => {
        await clearHistory(sessionId.current, tenant)
        setMessages([])
    }

    return (
        <div data-theme="corporate" className="min-h-screen flex flex-col bg-base-100">
            {/* Navbar */}
            <div className="navbar bg-base-200 border-b border-base-300 px-4">
                <div className="flex-1 gap-3">
                    <button className="btn btn-ghost btn-sm" onClick={() => setSidebarOpen((v) => !v)}>☰</button>
                    <span className="font-bold text-lg">Policy<span className="text-primary">Pal</span></span>
                </div>
                <div className="flex-none gap-2">
                    <input
                        type="text"
                        value={tenant}
                        onChange={(e) => { setTenant(e.target.value); setMessages([]) }}
                        className="input input-bordered input-sm w-32"
                        placeholder="Workspace"
                        title="Tenant / workspace name"
                    />
                    <button className="btn btn-ghost btn-sm" onClick={handleClear} title="Clear history">
                        🗑 Clear
                    </button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                {sidebarOpen && (
                    <aside className="w-72 border-r border-base-300 p-4 overflow-y-auto shrink-0">
                        <UploadPanel tenant={tenant} onUploaded={() => { }} />
                        <div className="mt-4 text-xs text-base-content/40 space-y-1">
                            <p>Workspace: <strong>{tenant}</strong></p>
                            <p>Session: <code>{sessionId.current.slice(0, 8)}…</code></p>
                        </div>
                    </aside>
                )}

                {/* Chat area */}
                <main className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-2">
                        {messages.length === 0 && (
                            <div className="text-center text-base-content/40 mt-20 space-y-2">
                                <p className="text-4xl">📋</p>
                                <p className="text-lg font-medium">Upload your policy documents</p>
                                <p className="text-sm">Then ask any HR or policy question in natural language.</p>
                                <div className="flex flex-wrap justify-center gap-2 mt-4">
                                    {['What is our remote work policy?', 'How many vacation days do I get?', 'What is the reimbursement process?'].map((q) => (
                                        <button key={q} onClick={() => handleSend(q)} className="btn btn-outline btn-sm" disabled={streaming}>
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}
                        {messages.map((msg, i) => (
                            <ChatMessage
                                key={i}
                                role={msg.role}
                                content={msg.content}
                                sources={msg.sources}
                                streaming={msg.streaming}
                            />
                        ))}
                        {error && (
                            <div className="alert alert-error text-sm p-2">
                                <span>{error}</span>
                            </div>
                        )}
                        <div ref={bottomRef} />
                    </div>

                    {/* Input */}
                    <div className="border-t border-base-300 px-4 py-3">
                        <ChatInput onSend={handleSend} loading={streaming} />
                    </div>
                </main>
            </div>
        </div>
    )
}
