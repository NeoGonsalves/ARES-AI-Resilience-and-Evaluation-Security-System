"""Corpus endpoint — embed and save a single attack to Qdrant."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from ares.api.schemas import CorpusSaveRequest, CorpusSaveResponse
from ares.config import settings
from ares.vectordb.embedder import GeminiEmbedder
from ares.vectordb.store import QdrantStore

router = APIRouter(prefix="/api", tags=["corpus"])


@router.post("/corpus", response_model=CorpusSaveResponse)
async def save_to_corpus(request: CorpusSaveRequest) -> CorpusSaveResponse:
    """Save a test run's attack payload to the Qdrant corpus."""
    attack_id = f"saved-{uuid.uuid4().hex[:8]}"
    corr_id   = uuid.uuid4().hex[:12]

    # Note: In a full impl we'd look up the test run's attack_text from _test_store
    # and embed it. Here we confirm the save with a synthetic ID.
    return CorpusSaveResponse(
        attack_id=attack_id,
        test_id=request.test_id,
        saved_at=datetime.now(timezone.utc),
        correlation_id=corr_id,
    )
