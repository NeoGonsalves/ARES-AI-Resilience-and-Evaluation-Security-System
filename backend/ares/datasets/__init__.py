"""
ARES Datasets & Corpus Ingestion Module.
"""

from ares.datasets.benchmarks import BenchmarkRecord, generate_benchmark_corpus
from ares.datasets.ingestor import CorpusIngestor, IngestionReport

__all__ = [
    "BenchmarkRecord",
    "generate_benchmark_corpus",
    "CorpusIngestor",
    "IngestionReport",
]
