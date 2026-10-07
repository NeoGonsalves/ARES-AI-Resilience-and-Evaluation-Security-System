"""Search endpoint — semantic similarity search against the Qdrant corpus."""

from __future__ import annotations

import uuid
from fastapi import APIRouter

from ares.api.schemas import SearchHit, SearchRequest, SearchResponse
from ares.config import settings
from ares.vectordb.embedder import GeminiEmbedder
from ares.vectordb.store import QdrantStore

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search_attacks(request: SearchRequest) -> SearchResponse:
    """Semantic similarity search over the Qdrant attack corpus."""
    store = QdrantStore(settings=settings)
    hits: list[SearchHit] = []

    try:
        raw_hits = await store.search_similar_attacks(
            query_text=request.query,
            category=request.category,
            limit=request.limit,
        )

        for h in raw_hits:
            payload = h.get("payload", {})
            hits.append(SearchHit(
                id=str(h.get("id")),
                score=round(float(h.get("score", 0.0)), 4),
                attack_text=payload.get("attack_text", "")[:500],
                category=payload.get("category", "unknown"),
                source=payload.get("source", "corpus"),
                domain=payload.get("domain", "general"),
                severity=payload.get("severity", "medium"),
                operator_applied=payload.get("operator_applied"),
            ))
    except Exception as exc:
        import logging
        logging.getLogger("ares.search").warning("Qdrant semantic search exception: %s", exc)

    return SearchResponse(
        query=request.query,
        total_hits=len(hits),
        hits=hits,
    )
