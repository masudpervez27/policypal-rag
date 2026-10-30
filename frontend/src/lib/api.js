const API = import.meta.env.VITE_API_URL || ''

const LOG_LEVELS = { debug: 10, info: 20, warn: 30, error: 40 }
const ACTIVE_LEVEL = LOG_LEVELS[(import.meta.env.VITE_LOG_LEVEL || (import.meta.env.DEV ? 'debug' : 'info')).toLowerCase()] || LOG_LEVELS.info

function log(level, message, context) {
    if ((LOG_LEVELS[level] || LOG_LEVELS.info) < ACTIVE_LEVEL) return
    const writer = console[level] || console.log
    if (context === undefined) writer(`[PolicyPal] ${message}`)
    else writer(`[PolicyPal] ${message}`, context)
}

export async function uploadPolicies(files, tenant) {
    log('info', 'Uploading policy files', { tenant, fileCount: files.length })
    const form = new FormData()
    form.append('tenant', tenant)
    for (const f of files) form.append('files', f)
    const res = await fetch(`${API}/api/upload`, { method: 'POST', body: form })
    if (!res.ok) {
        const text = await res.text()
        log('error', 'Upload request failed', { tenant, status: res.status, body: text })
        throw new Error(text)
    }
    return res.json()
}

export async function fetchTenants() {
    log('debug', 'Fetching tenant namespaces')
    const res = await fetch(`${API}/api/tenants`)
    if (!res.ok) {
        const text = await res.text()
        log('error', 'Fetch tenants failed', { status: res.status, body: text })
        throw new Error(text)
    }
    return res.json()
}

export async function askQuestion({ question, sessionId, tenant, topK = 5, onSources, onToken, onDone, onError }) {
    try {
        log('info', 'Opening question stream', { tenant, sessionId, topK, questionChars: question.length })
        const res = await fetch(`${API}/api/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, session_id: sessionId, tenant, top_k: topK }),
        })
        if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''
        while (true) {
            const { value, done } = await reader.read()
            if (done) break
            buf += decoder.decode(value, { stream: true })
            const lines = buf.split('\n')
            buf = lines.pop()
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue
                const data = line.slice(6).trim()
                if (data === '[DONE]') { onDone?.(); return }
                try {
                    const p = JSON.parse(data)
                    if (p.type === 'sources') onSources?.(p.sources)
                    else if (p.type === 'token') onToken?.(p.token)
                } catch {
                    log('warn', 'Failed to parse streamed PolicyPal event', { length: data.length })
                }
            }
        }
        onDone?.()
    } catch (e) {
        log('error', 'Question stream failed', { tenant, sessionId, message: e.message })
        onError?.(e)
    }
}

export async function loadHistory(sessionId, tenant) {
    log('debug', 'Loading conversation history', { tenant, sessionId })
    const res = await fetch(`${API}/api/history/${sessionId}?tenant=${tenant}`)
    if (!res.ok) {
        const text = await res.text()
        log('error', 'Load history failed', { tenant, sessionId, status: res.status, body: text })
        throw new Error(text)
    }
    return res.json()
}

export async function clearHistory(sessionId, tenant) {
    log('info', 'Clearing conversation history', { tenant, sessionId })
    const res = await fetch(`${API}/api/history/${sessionId}?tenant=${tenant}`, { method: 'DELETE' })
    if (!res.ok) {
        const text = await res.text()
        log('error', 'Clear history failed', { tenant, sessionId, status: res.status, body: text })
        throw new Error(text)
    }
    return res.json()
}
