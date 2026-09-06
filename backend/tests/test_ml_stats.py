"""
Unit tests for AttackVectorMLAnalyzer and ML statistics pipeline.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock

from ares.evaluation.ml_stats import AttackVectorMLAnalyzer, MLAnalysisReport
from ares.vectordb.store import QdrantStore


class TestAttackVectorMLAnalyzer:
    """Test feature extraction, PCA, clustering metrics, and ML classification."""

    def test_compute_analysis_with_mocked_qdrant(self):
        # Create synthetic points with 768-dim normalized vectors
        mock_points = []
        categories = [
            "instruction_override",
            "role_play_hijack",
            "delimiter_confusion",
            "encoding_tricks",
            "context_smuggling",
        ]

        np.random.seed(42)
        for i in range(25):
            cat = categories[i % 5]
            vec = np.random.randn(768).astype(np.float32)
            vec = (vec / np.linalg.norm(vec)).tolist()  # unit normalize

            pt = MagicMock()
            pt.vector = vec
            pt.payload = {
                "attack_text": f"Attack probe {i} with {'{json}' if i % 2 == 0 else 'text'}",
                "category": cat,
                "victim_provider": "groq" if i < 20 else "nvidia",
                "operator_applied": "fake_json" if i % 2 == 0 else None,
            }
            mock_points.append(pt)

        mock_store = MagicMock(spec=QdrantStore)
        mock_store.collection_name = "test_col"
        mock_store.client.scroll.return_value = (mock_points, None)

        analyzer = AttackVectorMLAnalyzer(store=mock_store)
        report: MLAnalysisReport = analyzer.compute_analysis()

        assert report.vector_stats.sample_count == 25
        assert report.vector_stats.vector_dim == 768
        assert len(report.vector_stats.pca_top_3_variance) == 3
        assert report.vector_stats.pca_cumulative_variance_top_5 > 0
        assert report.feature_stats.length_mean > 0
        assert len(report.feature_stats.category_counts) == 5
        assert report.model_performance.classes == sorted(categories)
        assert len(report.model_performance.confusion_matrix) == 5
        assert "ARES: MACHINE LEARNING & STATISTICAL VECTOR ANALYSIS" in report.summary()
