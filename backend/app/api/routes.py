import json
import logging
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from ..core.database import append_message, clear_history, get_history
from ..models.schemas import (
    AskRequest,
    HistoryClearResponse,
    SourceChunk,
    TenantsResponse,
    UploadResponse,
)
from ..services.indexer import index_file, list_tenants
from ..services.retrieval import retrieve
from ..services.llm import stream_answer

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/tenants", response_model=TenantsResponse)
async def get_tenants():
    tenants = list_tenants()
    logger.info("Listed %d tenant namespaces", len(tenants))
    return TenantsResponse(tenants=tenants)


@router.post("/upload", response_model=UploadResponse)
async def upload_policies(
    tenant: str = Form(default="default"),
    files: list[UploadFile] = File(...),
):
    """Upload one or more policy documents for a tenant."""
    if not tenant or not tenant.replace("_", "").isalnum():
        logger.warning("Rejected invalid tenant name: %s", tenant)
        raise HTTPException(status_code=422, detail="Tenant name must be alphanumeric.")

    logger.info("Uploading %d policy files for tenant '%s'", len(files), tenant)

    total_chunks = 0
    indexed_files: list[str] = []

    for file in files:
        from pathlib import Path
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            logger.warning("Rejected file %s with disallowed suffix %s", file.filename or "unknown", suffix)
            raise HTTPException(
                status_code=422,
                detail=f"File type '{suffix}' not allowed. Use PDF, TXT, or MD.",
            )
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning("Rejected oversized file %s (%d bytes)", file.filename or "unknown", len(content))
            raise HTTPException(status_code=413, detail=f"{file.filename} exceeds 10 MB limit.")

        n = index_file(content, file.filename or "unknown", tenant)
        total_chunks += n
        indexed_files.append(file.filename or "unknown")

    logger.info("Indexed %d chunks across %d files for tenant '%s'", total_chunks, len(indexed_files), tenant)

    return UploadResponse(
        tenant=tenant,
        chunks_indexed=total_chunks,
        files=indexed_files,
        message=f"Indexed {total_chunks} chunks from {len(indexed_files)} file(s) into namespace '{tenant}'.",
    )


@router.post("/ask")
async def ask(req: AskRequest):
    """
    Streaming endpoint: retrieve → Groq LLM with conversation memory.
    Returns SSE stream.
    """
    logger.info("Received ask request for tenant '%s' (session=%s, chars=%d)", req.tenant, req.session_id, len(req.question))
    chunks = retrieve(req.question, req.tenant, top_k=req.top_k)

    if not chunks:
        logger.warning("No policy chunks found for tenant '%s'", req.tenant)
        async def no_results():
            yield "data: " + json.dumps({"type": "token", "token": "⚠️ No policy documents found for this workspace. Please upload your policy PDFs first."}) + "\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_results(), media_type="text/event-stream")

    history = get_history(req.session_id, req.tenant, limit=10)
    logger.info("Retrieved %d policy chunks and %d history messages", len(chunks), len(history))

    sources_payload = [
        {"source_file": c["source_file"], "page": c["page"], "score": c["score"]}
        for c in chunks
    ]

    async def event_stream():
        full_answer = ""
        yield "data: " + json.dumps({"type": "sources", "sources": sources_payload}) + "\n\n"
        for token in stream_answer(req.question, chunks, history):
            full_answer += token
            yield "data: " + json.dumps({"type": "token", "token": token}) + "\n\n"
        yield "data: [DONE]\n\n"

        # Persist conversation turn to PostgreSQL
        append_message(req.session_id, req.tenant, "user", req.question)
        append_message(req.session_id, req.tenant, "assistant", full_answer)
        logger.info("Persisted conversation turn for tenant '%s' session '%s'", req.tenant, req.session_id)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history/{session_id}")
async def get_conv_history(session_id: str, tenant: str = "default", limit: int = 20):
    msgs = get_history(session_id, tenant, limit=limit)
    logger.info("Loaded %d history messages for tenant '%s' session '%s'", len(msgs), tenant, session_id)
    return {"session_id": session_id, "tenant": tenant, "messages": msgs}


@router.delete("/history/{session_id}", response_model=HistoryClearResponse)
async def clear_conv_history(session_id: str, tenant: str = "default"):
    n = clear_history(session_id, tenant)
    logger.info("Cleared %d history messages for tenant '%s' session '%s'", n, tenant, session_id)
    return HistoryClearResponse(deleted=n, session_id=session_id)
