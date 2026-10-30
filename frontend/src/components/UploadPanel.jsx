import { useState, useRef } from 'react'
import { uploadPolicies } from '../lib/api'

export default function UploadPanel({ tenant, onUploaded }) {
    const [files, setFiles] = useState([])
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const inputRef = useRef()

    const handleUpload = async () => {
        if (!files.length) return
        setLoading(true)
        setError(null)
        try {
            const data = await uploadPolicies(files, tenant)
            setResult(data)
            setFiles([])
            inputRef.current.value = ''
            onUploaded?.(data)
        } catch (e) {
            setError(e.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card bg-base-200 shadow p-4 space-y-3">
            <h3 className="font-semibold text-sm">Upload Policy Documents</h3>
            <input
                ref={inputRef}
                type="file"
                multiple
                accept=".pdf,.txt,.md"
                className="file-input file-input-bordered file-input-sm w-full"
                onChange={(e) => setFiles(Array.from(e.target.files))}
            />
            {files.length > 0 && (
                <p className="text-xs text-base-content/60">{files.length} file(s) selected</p>
            )}
            <button
                className={`btn btn-primary btn-sm w-full ${loading ? 'loading' : ''}`}
                onClick={handleUpload}
                disabled={loading || !files.length}
            >
                {loading ? 'Indexing...' : 'Upload & Index'}
            </button>
            {result && (
                <div className="alert alert-success text-xs p-2">
                    ✅ {result.message}
                </div>
            )}
            {error && (
                <div className="alert alert-error text-xs p-2">
                    ❌ {error}
                </div>
            )}
            <p className="text-xs text-base-content/40">Supports PDF, TXT, MD — max 10 MB each</p>
        </div>
    )
}
