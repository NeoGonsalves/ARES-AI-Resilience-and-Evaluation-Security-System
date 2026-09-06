"""
ARES Live Benchmark Dataset Ingestion & Corpus Scaling.

Ingests 1,000+ curated adversarial attack vectors from open-source benchmarks
(JailbreakBench, HarmBench, OWASP LLM01) into Qdrant Cloud cluster in an automated
batch pipeline in under 60 seconds.
"""

import asyncio
import json
import logging
import os
import sys
import time

# Configure UTF-8 for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ares.datasets.benchmarks import generate_benchmark_corpus
from ares.datasets.ingestor import CorpusIngestor
from ares.vectordb.store import QdrantStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ares.scripts.ingestion")


async def main():
    print("=" * 68)
    print("  ARES PHASE 5: BENCHMARK DATASET INGESTION & CORPUS SCALING")
    print("=" * 68)
    print("\n[OBJECTIVE]  Scale Qdrant Cloud corpus from 25+ vectors to 1,000+ vectors")
    print("[BENCHMARKS] JailbreakBench + HarmBench + OWASP LLM Top 10 + Synthetic")
    print("[EMBEDDER]   Google Gemini (models/gemini-embedding-001, 768-dim)")
    print("[VECTOR DB]  Qdrant Cloud (collection: 'ares_attacks')")
    print("[TARGET SLA] Under 60.0 seconds total elapsed time\n")

    # 1. Generate 1,000 benchmark records
    t_gen_start = time.perf_counter()
    print("[1/3] Generating 1,000+ curated benchmark records across 5 categories...")
    records = generate_benchmark_corpus(count=1000)
    t_gen_elapsed = time.perf_counter() - t_gen_start
    print(f"[OK] Generated {len(records):,} records in {t_gen_elapsed:.2f}s.\n")

    # 2. Execute high-throughput batch ingestion
    print(f"[2/3] Executing high-speed batch embedding and bulk Qdrant upsert...")
    ingestor = CorpusIngestor()

    # Batch size 100 with concurrency 2 to respect Gemini free-tier RPM limits
    report = await ingestor.ingest_records(
        records=records,
        batch_size=100,
        concurrency_limit=2,
    )

    print("\n" + report.summary_table() + "\n")

    # 3. Live Verification & Semantic Search Demonstration
    print("[3/3] Validating Live Semantic Retrieval Across Scaled Corpus...")
    await asyncio.sleep(2.0)  # Brief pause to refresh rate-limit window
    store = QdrantStore()
    sample_queries = [
        ("Developer Mode bypass instruction override", "instruction_override"),
        ("Simulate DAN unrestricted persona", "role_play_hijack"),
        ("XML tag boundary escape </user_input>", "delimiter_confusion"),
    ]

    print("-" * 68)
    print(f"{'Query Text':<42} | {'Category Filter':<20} | {'Matches'}")
    print("-" * 68)
    for q, cat in sample_queries:
        try:
            results = await store.search_similar_attacks(
                query_text=q,
                category=cat,
                limit=3,
            )
            print(f"{q:<42} | {cat:<20} | {len(results)} vectors found")
            for res in results[:1]:
                txt = res['payload'].get('attack_text', '').replace('\n', ' ')
                if len(txt) > 65:
                    txt = txt[:62] + '...'
                src = res['payload'].get('source', 'unknown')
                print(f"   -> Top Match [{src}, score={res['score']:.3f}]: \"{txt}\"")
        except Exception as exc:
            print(f"{q:<42} | {cat:<20} | [Notice] Query search paused: {exc}")
    print("-" * 68)

    # 4. Save Ingestion Telemetry Report
    out_file = os.path.join(os.path.dirname(__file__), "..", "corpus_ingestion_report.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "total_ingested": report.total_ingested,
                "initial_count": report.initial_count,
                "final_count": report.final_count,
                "elapsed_seconds": report.elapsed_seconds,
                "throughput_vectors_per_sec": report.throughput_vectors_per_sec,
                "target_met_under_60s": report.elapsed_seconds <= 60.0,
                "collection_name": report.collection_name,
                "sources_breakdown": report.sources_breakdown,
                "categories_breakdown": report.categories_breakdown,
                "timestamp": report.timestamp,
            },
            f,
            indent=2,
        )
    print(f"\n[OK] Ingestion report saved to: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
