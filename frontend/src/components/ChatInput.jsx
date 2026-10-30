import { useState, useRef, useEffect } from 'react'

export default function ChatInput({ onSend, loading }) {
    const [text, setText] = useState('')
    const textareaRef = useRef()

    const submit = () => {
        const q = text.trim()
        if (!q || loading) return
        onSend(q)
        setText('')
    }

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
        }
    }

    return (
        <div className="flex gap-2 items-end">
            <textarea
                ref={textareaRef}
                rows={2}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about a policy… (Enter to send, Shift+Enter for newline)"
                className="textarea textarea-bordered flex-1 resize-none text-sm"
                disabled={loading}
                maxLength={1000}
            />
            <button
                onClick={submit}
                className={`btn btn-primary ${loading ? 'loading' : ''}`}
                disabled={loading || !text.trim()}
            >
                {loading ? '' : 'Send'}
            </button>
        </div>
    )
}
