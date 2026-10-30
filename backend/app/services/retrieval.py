"""
Vector retrieval from the tenant-namespaced Qdrant collection.
"""

import logging

from ..core.embeddings import embed_query
from .indexer import get_qdrant, collection_name

logger = logging.getLogger(__name__)


def retrieve(query: str, tenant: str, top_k: int = 5) -> list[dict]:
    """Return top_k chunks from the tenant's Qdrant collection."""
    client = get_qdrant()
    cname = collection_name(tenant)

    # Check collection exists
    existing = [c.name for c in client.get_collections().collections]
    if cname not in existing:
        logger.warning("Tenant collection %s does not exist", cname)
        return []

    logger.info("Running retrieval for tenant '%s' (query_chars=%d, top_k=%d)", tenant, len(query), top_k)
    query_vector = embed_query(query)
    hits = client.search(
        collection_name=cname,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
    )

    results = [
        {
            "content": hit.payload["content"],
            "source_file": hit.payload.get("source_file", ""),
            "page": hit.payload.get("page"),
            "score": round(float(hit.score), 4),
        }
        for hit in hits
    ]
    logger.info("Retrieved %d chunks for tenant '%s'", len(results), tenant)
    return results
