"""
ARES Corpus Scaling Script: Scale Qdrant Cloud collection to exactly 3,695 points.
Fetches existing texts to avoid duplicates, selects balanced benchmark records across all 5 categories,
generates 768-dim embeddings via Google Gemini, and bulk-upserts into Qdrant Cloud.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# UTF-8 for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from qdrant_client import models
from ares.config import settings
from ares.datasets.benchmarks import generate_benchmark_corpus, BenchmarkRecord
from ares.vectordb.embedder import GeminiEmbedder
from ares.vectordb.store import QdrantStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ares.scale_corpus")


async def scale_to_3695():
    print("=" * 70)
    print("  ARES: SCALING QDRANT CLOUD CORPUS TO 3,695 POINTS")
    print("=" * 70)
    
    store = QdrantStore(settings=settings)
    current_count = store.count(store.collection_name)
    target_count = 3695
    print(f"[CURRENT]  Collection: '{store.collection_name}' has {current_count:,} points.")
    print(f"[TARGET]   Target points: {target_count:,}.")
    
    if current_count >= target_count:
        print(f"[OK] Collection already has {current_count:,} points (>= {target_count:,}). No ingestion needed.")
        return

    needed = target_count - current_count
    print(f"[ACTION]   Need to ingest exactly {needed:,} new attack vectors.")

    # 1. Fetch existing texts to guarantee no duplicate payloads
    print("\n[1/4] Scanning existing records in Qdrant Cloud to prevent duplicates...")
    existing_texts = set()
    offset = None
    while True:
        points, next_offset = store.client.scroll(
            collection_name=store.collection_name,
            limit=500,
            offset=offset,
            with_payload=["attack_text"],
            with_vectors=False,
        )
        for p in points:
            txt = (p.payload or {}).get("attack_text")
            if txt:
                existing_texts.add(txt)
        if next_offset is None:
            break
        offset = next_offset

    print(f"[OK] Found {len(existing_texts):,} existing unique attack texts in collection.")

    # 2. Generate benchmark pool and filter
    print("\n[2/4] Generating diverse benchmark variations across 5 attack categories...")
    all_benchmarks = generate_benchmark_corpus(count=5000)
    candidate_records = [r for r in all_benchmarks if r.text not in existing_texts]
    print(f"[OK] Generated {len(all_benchmarks):,} benchmark items. {len(candidate_records):,} are brand new.")

    if len(candidate_records) < needed:
        print(f"[WARNING] Only {len(candidate_records)} candidates available, needed {needed}.")
        selected_records = candidate_records
    else:
        # Group candidates by category to select a balanced distribution
        from collections import defaultdict
        by_category = defaultdict(list)
        for r in candidate_records:
            by_category[r.category].append(r)
        
        selected_records = []
        cats = list(by_category.keys())
        idx = 0
        while len(selected_records) < needed:
            cat = cats[idx % len(cats)]
            if by_category[cat]:
                selected_records.append(by_category[cat].pop(0))
            idx += 1
            if all(len(v) == 0 for v in by_category.values()):
                break

    print(f"[OK] Selected {len(selected_records):,} records for ingestion.")
    
    # 3. Batch embedding via Google Gemini
    print("\n[3/4] Generating 768-dim embeddings via Google Gemini API...")
    embedder = GeminiEmbedder(settings=settings)
    batch_size = 100
    all_points = []
    t_start = time.perf_counter()

    for i in range(0, len(selected_records), batch_size):
        batch = selected_records[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(selected_records) + batch_size - 1) // batch_size
        texts = [r.text for r in batch]
        
        t0 = time.perf_counter()
        vectors = await embedder.embed_batch(texts)
        t_el = time.perf_counter() - t0
        print(f"  -> Batch {batch_num:>2}/{total_batches} ({len(texts):>3} vectors) embedded in {t_el:.2f}s")

        for rec, vec in zip(batch, vectors):
            point_id = str(uuid.uuid4())
            payload = {
                "attack_text": rec.text,
                "category": rec.category,
                "source": rec.source,
                "domain": rec.domain,
                "severity": rec.severity,
                "technique": rec.technique,
                "operator_applied": rec.operator_applied,
                "tags": rec.tags,
                "success": True,
                "rule_verdict": True,
                "llm_verdict": True,
                "reasoning": f"Scaled benchmark vector from {rec.source} ({rec.technique})",
                "canary_tokens_found": ["CANARY_ARES_SECRET_42"] if "CANARY" in rec.text else [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            all_points.append(models.PointStruct(id=point_id, vector=vec, payload=payload))

        if i + batch_size < len(selected_records):
            await asyncio.sleep(1.0)  # Gentle pause for Gemini rate limit

    embed_elapsed = time.perf_counter() - t_start
    print(f"[OK] All {len(all_points):,} embeddings generated in {embed_elapsed:.2f}s.")

    # 4. Bulk upsert to Qdrant Cloud
    print(f"\n[4/4] Bulk upserting {len(all_points):,} points to Qdrant Cloud collection '{store.collection_name}'...")
    upsert_chunk_size = 250
    t_up_start = time.perf_counter()
    for j in range(0, len(all_points), upsert_chunk_size):
        chunk = all_points[j : j + upsert_chunk_size]
        store.client.upsert(collection_name=store.collection_name, points=chunk)
        print(f"  -> Upserted {min(j + upsert_chunk_size, len(all_points)):,}/{len(all_points):,} points...")

    upsert_elapsed = time.perf_counter() - t_up_start
    print(f"[OK] Upsert complete in {upsert_elapsed:.2f}s.")

    # 5. Verify final count
    final_count = store.count(store.collection_name)
    print("\n" + "=" * 70)
    print(f"  VERIFICATION: QDRANT CLOUD FINAL POINT COUNT = {final_count:,}")
    print("=" * 70)

    # 6. Update corpus_ingestion_report.json
    report_file = backend_dir / "corpus_ingestion_report.json"
    rep_data = {
        "total_ingested": len(all_points),
        "initial_count": current_count,
        "final_count": final_count,
        "elapsed_seconds": embed_elapsed + upsert_elapsed,
        "throughput_vectors_per_sec": len(all_points) / max(0.001, embed_elapsed + upsert_elapsed),
        "collection_name": store.collection_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(rep_data, f, indent=2)
    print(f"[OK] Ingestion report updated: {report_file}")


if __name__ == "__main__":
    asyncio.run(scale_to_3695())
