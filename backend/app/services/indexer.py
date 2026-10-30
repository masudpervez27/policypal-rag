"""
Document indexer — uploads policy PDFs/TXTs, chunks them, and stores
in a Qdrant collection namespaced by tenant.
"""

import logging
import tempfile
import uuid
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ..core.config import settings
from ..core.embeddings import embed_texts

logger = logging.getLogger(__name__)

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=100,
)

_qdrant: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        logger.info("Initializing Qdrant client for PolicyPal")
        _qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return _qdrant


def collection_name(tenant: str) -> str:
    # Sanitise tenant name to safe characters
    safe = "".join(c if c.isalnum() or c == "_" else "_" for c in tenant.lower())
    return f"{settings.qdrant_collection_prefix}_{safe}"


def ensure_collection(tenant: str) -> None:
    client = get_qdrant()
    cname = collection_name(tenant)
    existing = [c.name for c in client.get_collections().collections]
    if cname not in existing:
        logger.info("Creating Qdrant collection %s", cname)
        client.create_collection(
            collection_name=cname,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )


def list_tenants() -> list[str]:
    client = get_qdrant()
    prefix = settings.qdrant_collection_prefix + "_"
    return [
        c.name[len(prefix):]
        for c in client.get_collections().collections
        if c.name.startswith(prefix)
    ]


def index_file(file_bytes: bytes, filename: str, tenant: str) -> int:
    """Chunk and embed a single file, upsert to Qdrant. Returns chunk count."""
    ensure_collection(tenant)
    suffix = Path(filename).suffix.lower()
    logger.info("Indexing policy file %s for tenant '%s'", filename, tenant)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        if suffix == ".pdf":
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()
        else:
            loader = TextLoader(tmp_path, encoding="utf-8")
            docs = loader.load()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    for doc in docs:
        doc.metadata["source_file"] = filename

    chunks = SPLITTER.split_documents(docs)
    if not chunks:
        logger.warning("No chunks produced for %s", filename)
        return 0

    texts = [c.page_content for c in chunks]
    vectors = embed_texts(texts)
    cname = collection_name(tenant)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=v,
            payload={
                "content": c.page_content,
                "source_file": filename,
                "page": c.metadata.get("page"),
                "tenant": tenant,
            },
        )
        for c, v in zip(chunks, vectors)
    ]
    get_qdrant().upsert(collection_name=cname, points=points)
    logger.info("Indexed %d chunks for %s into collection %s", len(chunks), filename, cname)
    return len(chunks)
