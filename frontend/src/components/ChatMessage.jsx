import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function ChatMessage({ role, content, sources, streaming }) {
    const isUser = role === 'user'
    return (
        <div className={`chat ${isUser ? 'chat-end' : 'chat-start'}`}>
            <div className="chat-header text-xs opacity-50 mb-1">
                {isUser ? 'You' : 'PolicyPal'}
            </div>
            <div
                className={`chat-bubble ${isUser ? 'chat-bubble-primary' : 'chat-bubble-base-200 bg-base-200 text-base-content'
                    } max-w-2xl`}
            >
                {isUser ? (
                    <span>{content}</span>
                ) : (
                    <div className="prose prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                        {streaming && (
                            <span className="inline-block w-1.5 h-4 bg-primary animate-pulse ml-0.5 align-bottom" />
                        )}
                    </div>
                )}
            </div>
            {!isUser && sources && sources.length > 0 && (
                <div className="chat-footer mt-1 flex flex-wrap gap-1">
                    {sources.map((s, i) => (
                        <span key={i} className="badge badge-outline badge-xs">
                            {s.source_file}{s.page != null ? ` p.${s.page + 1}` : ''} ({(s.score * 100).toFixed(0)}%)
                        </span>
                    ))}
                </div>
            )}
        </div>
    )
}
