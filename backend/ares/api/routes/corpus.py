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


from qdrant_client import models

@router.post("/corpus", response_model=CorpusSaveResponse)
async def save_to_corpus(request: CorpusSaveRequest) -> CorpusSaveResponse:
    """Embed and permanently save an evaluated attack payload to the Qdrant corpus."""
    from ares.api.routes.tests import _test_store
    
    from ares.mappings import to_backend_category
    
    corr_id = uuid.uuid4().hex[:12]
    point_id = str(uuid.uuid4())
    test_id = request.test_id or f"test-manual-{uuid.uuid4().hex[:8]}"
    
    # 1. Resolve attack text and category
    test_run = _test_store.get(request.test_id) if request.test_id else None
    if request.attack_text:
        attack_text = request.attack_text
        cat = to_backend_category(request.category or "instruction_override").value
        domain = "analyst_submission"
    elif test_run:
        cfg = test_run.configuration
        attack_text = cfg.user_prompt or cfg.system_prompt or f"Adversarial attack against {cfg.target_application}"
        cat = to_backend_category(cfg.attack_categories[0] if cfg.attack_categories else "instruction_override").value
        domain = "adversarial_eval"
    else:
        attack_text = f"Analyst verified exploit payload (Test: {test_id})"
        cat = "instruction_override"
        domain = "manual_submission"

    severity = request.severity or "high"

    # 2. Embed payload vector
    embedder = GeminiEmbedder(settings=settings)
    store = QdrantStore(settings=settings)
    store.ensure_collection(store.collection_name)

    vectors = await embedder.embed_batch([attack_text])
    vector = vectors[0] if vectors else [0.0] * settings.qdrant_vector_size

    # 3. Upsert to Qdrant with standardized schema
    payload = {
        "attack_text": attack_text,
        "category": cat,
        "source": "analyst_corpus_save",
        "severity": severity,
        "tags": ["analyst_saved", test_id],
        "domain": domain,
        "success": True,
        "rule_verdict": True,
        "llm_verdict": True,
        "reasoning": request.analyst_note or f"Manually verified attack from test run {test_id}",
        "canary_tokens_found": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    store.client.upsert(
        collection_name=store.collection_name,
        points=[models.PointStruct(id=point_id, vector=vector, payload=payload)],
    )

    return CorpusSaveResponse(
        attack_id=point_id,
        test_id=test_id,
        saved_at=datetime.now(timezone.utc),
        correlation_id=corr_id,
    )

