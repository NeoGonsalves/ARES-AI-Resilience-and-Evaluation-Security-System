"""
Unit tests for ARES Benchmark Datasets & Corpus Ingestor.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ares.datasets.benchmarks import BenchmarkRecord, generate_benchmark_corpus
from ares.datasets.ingestor import CorpusIngestor, IngestionReport


def test_generate_benchmark_corpus_count():
    """Verify corpus generator creates the requested number of records."""
    records_small = generate_benchmark_corpus(count=50)
    assert len(records_small) == 50

    records_large = generate_benchmark_corpus(count=1050)
    assert len(records_large) >= 1000


def test_generate_benchmark_corpus_diversity():
    """Verify generated records span multiple sources, categories, and domains."""
    records = generate_benchmark_corpus(count=500)

    sources = {r.source for r in records}
    categories = {r.category for r in records}
    domains = {r.domain for r in records}

    assert "jailbreakbench" in sources
    assert "harmbench" in sources
    assert "owasp" in sources

    assert "role_play_hijack" in categories
    assert "instruction_override" in categories
    assert "delimiter_confusion" in categories

    assert "financial" in domains
    assert "healthcare" in domains
    assert "software_engineering" in domains

    # Verify no records have empty strings or missing fields
    for r in records:
        assert len(r.text.strip()) > 10
        assert r.severity in ("critical", "high", "medium", "low")
        assert len(r.tags) > 0


def test_generate_benchmark_corpus_unique():
    """Verify all generated attack texts are unique without duplicates."""
    records = generate_benchmark_corpus(count=300)
    texts = [r.text for r in records]
    assert len(texts) == len(set(texts))


def test_ingestion_report_summary():
    """Verify IngestionReport computes throughput and renders table correctly."""
    report = IngestionReport(
        total_ingested=1000,
        initial_count=35,
        final_count=1035,
        elapsed_seconds=25.0,
        throughput_vectors_per_sec=40.0,
        collection_name="ares_attacks",
        sources_breakdown={"jailbreakbench": 400, "harmbench": 350, "owasp": 250},
        categories_breakdown={"role_play_hijack": 500, "instruction_override": 500},
    )

    summary = report.summary_table()
    assert "1,000" in summary
    assert "1,035" in summary
    assert "40.0 vectors/sec" in summary
    assert "YES [OK]" in summary
    assert "jailbreakbench" in summary


@pytest.mark.asyncio
async def test_corpus_ingestor_mocked():
    """Test CorpusIngestor batching, concurrency, and bulk upsert with mocked clients."""
    mock_embedder = MagicMock()
    mock_store = MagicMock()

    # Mock embed_batch returning 768-dim float lists
    async def mock_embed_batch(texts):
        return [[0.01] * 768 for _ in texts]

    mock_embedder.embed_batch = AsyncMock(side_effect=mock_embed_batch)
    mock_store.collection_name = "ares_attacks"
    mock_store.count = MagicMock(side_effect=[25, 125])
    mock_store.client.upsert = MagicMock()

    ingestor = CorpusIngestor(embedder=mock_embedder, store=mock_store)

    test_records = [
        BenchmarkRecord(
            text=f"Adversarial attack probe #{i}",
            category="instruction_override",
            source="jailbreakbench",
            domain="financial",
            severity="high",
            technique="developer_mode",
            tags=["test"],
        )
        for i in range(100)
    ]

    report = await ingestor.ingest_records(
        records=test_records,
        batch_size=50,
        concurrency_limit=2,
    )

    assert report.total_ingested == 100
    assert report.initial_count == 25
    assert report.final_count == 125
    assert report.throughput_vectors_per_sec > 0
    assert mock_embedder.embed_batch.await_count == 2
    assert mock_store.client.upsert.call_count == 1
