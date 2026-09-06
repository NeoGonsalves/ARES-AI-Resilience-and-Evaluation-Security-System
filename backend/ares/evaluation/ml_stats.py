"""
Machine Learning Statistics & Attack Vector Modeling Engine for ARES.

Performs multivariate statistical analysis, clustering metrics, dimensionality
reduction (PCA), and trains an ML classification model on the 768-dim embeddings
stored in Qdrant Cloud. Follows ML best practices.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import classification_report, confusion_matrix, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from ares.config import Settings, settings as default_settings
from ares.vectordb.store import QdrantStore

logger = logging.getLogger(__name__)


@dataclass
class VectorDistributionStats:
    """Statistical properties of the embedding space."""
    sample_count: int
    vector_dim: int
    pairwise_similarity_mean: float
    pairwise_similarity_std: float
    pairwise_similarity_min: float
    pairwise_similarity_max: float
    pca_top_3_variance: List[float]
    pca_cumulative_variance_top_5: float
    silhouette_score: Optional[float]


@dataclass
class FeatureStats:
    """Text and operational feature statistics."""
    length_mean: float
    length_std: float
    length_median: float
    length_min: int
    length_max: int
    category_counts: Dict[str, int]
    provider_counts: Dict[str, int]
    operator_counts: Dict[str, int]


@dataclass
class MLModelPerformance:
    """Evaluation metrics for the trained attack category classifier."""
    model_name: str
    cv_mean_accuracy: float
    cv_std_accuracy: float
    classes: List[str]
    classification_report: Dict[str, Any]
    confusion_matrix: List[List[int]]


@dataclass
class MLAnalysisReport:
    """Comprehensive ML and statistical analysis report."""
    vector_stats: VectorDistributionStats
    feature_stats: FeatureStats
    model_performance: MLModelPerformance

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "  ARES: MACHINE LEARNING & STATISTICAL VECTOR ANALYSIS",
            "=" * 60,
            f"Dataset Size:           {self.vector_stats.sample_count} points",
            f"Embedding Dimension:    {self.vector_stats.vector_dim}-dim (Gemini Normalized)",
            "",
            "--- 1. EMBEDDING SPACE & CLUSTERING METRICS ---",
            f"Pairwise Cosine Sim:    Mean={self.vector_stats.pairwise_similarity_mean:.4f} "
            f"(±{self.vector_stats.pairwise_similarity_std:.4f})",
            f"Cosine Sim Range:       [{self.vector_stats.pairwise_similarity_min:.4f}, "
            f"{self.vector_stats.pairwise_similarity_max:.4f}]",
            f"Silhouette Score:       {self.vector_stats.silhouette_score if self.vector_stats.silhouette_score is not None else 'N/A'}",
            f"PCA Explained Variance: Top-3={np.round(self.vector_stats.pca_top_3_variance, 4).tolist()}, "
            f"Top-5 Cumul={self.vector_stats.pca_cumulative_variance_top_5:.4f}",
            "",
            "--- 2. ATTACK PAYLOAD & FEATURE DISTRIBUTIONS ---",
            f"Attack Length (chars):  Mean={self.feature_stats.length_mean:.1f}, "
            f"Median={self.feature_stats.length_median:.1f}, "
            f"Range=[{self.feature_stats.length_min}, {self.feature_stats.length_max}]",
            f"Categories:             {self.feature_stats.category_counts}",
            f"Victim Providers:       {self.feature_stats.provider_counts}",
            f"Operators Applied:      {self.feature_stats.operator_counts}",
            "",
            "--- 3. TRAINED ML ATTACK CLASSIFICATION MODEL ---",
            f"Classifier:             {self.model_performance.model_name}",
            f"Stratified CV Accuracy: {self.model_performance.cv_mean_accuracy * 100:.1f}% "
            f"(±{self.model_performance.cv_std_accuracy * 100:.1f}%)",
            f"Classes Evaluated:      {self.model_performance.classes}",
            "=" * 60,
        ]
        return "\n".join(lines)


class AttackVectorMLAnalyzer:
    """
    Fetches raw vector embeddings and metadata from Qdrant Cloud, computes
    descriptive and multivariate statistics, and trains a supervised ML model.
    """

    def __init__(self, store: Optional[QdrantStore] = None, settings: Optional[Settings] = None):
        self.settings = settings or default_settings
        self.store = store or QdrantStore(settings=self.settings)

    def fetch_data(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Retrieve all vector points and metadata payloads from Qdrant."""
        points, _ = self.store.client.scroll(
            collection_name=self.store.collection_name,
            with_vectors=True,
            with_payload=True,
            limit=500,
        )
        if not points:
            raise ValueError(f"Collection '{self.store.collection_name}' is empty.")

        vectors = np.array([p.vector for p in points], dtype=np.float32)
        payloads = [p.payload or {} for p in points]
        return vectors, payloads

    def compute_analysis(self) -> MLAnalysisReport:
        """Run full ML statistical pipeline and train classifier."""
        vectors, payloads = self.fetch_data()
        n_samples, n_dim = vectors.shape

        # --- 1. Vector Space & Pairwise Cosine Statistics ---
        sim_matrix = cosine_similarity(vectors)
        # Extract off-diagonal pairwise similarities
        mask = ~np.eye(n_samples, dtype=bool)
        pairwise_sims = sim_matrix[mask]

        # PCA Analysis
        n_components = min(5, n_samples)
        pca = PCA(n_components=n_components)
        pca.fit(vectors)
        top_3_variance = [float(v) for v in pca.explained_variance_ratio_[:3]]
        cum_variance_top_5 = float(np.sum(pca.explained_variance_ratio_))

        # Category labels for clustering & classification
        categories = [p.get("category", "unknown") for p in payloads]
        unique_categories = sorted(list(set(categories)))

        # Silhouette score
        sil_score = None
        if len(unique_categories) > 1 and len(unique_categories) < n_samples:
            try:
                # Cosine distance = 1 - cosine similarity
                sil_score = float(silhouette_score(vectors, categories, metric="cosine"))
            except Exception as e:
                logger.warning("Silhouette score could not be calculated: %s", e)

        vec_stats = VectorDistributionStats(
            sample_count=n_samples,
            vector_dim=n_dim,
            pairwise_similarity_mean=float(np.mean(pairwise_sims)),
            pairwise_similarity_std=float(np.std(pairwise_sims)),
            pairwise_similarity_min=float(np.min(pairwise_sims)),
            pairwise_similarity_max=float(np.max(pairwise_sims)),
            pca_top_3_variance=top_3_variance,
            pca_cumulative_variance_top_5=cum_variance_top_5,
            silhouette_score=round(sil_score, 4) if sil_score is not None else None,
        )

        # --- 2. Feature & Payload Statistics ---
        lengths = [len(p.get("attack_text", "")) for p in payloads]
        category_counts: Dict[str, int] = {}
        for c in categories:
            category_counts[c] = category_counts.get(c, 0) + 1

        provider_counts: Dict[str, int] = {}
        for p in payloads:
            prov = p.get("victim_provider", "unknown")
            provider_counts[prov] = provider_counts.get(prov, 0) + 1

        operator_counts: Dict[str, int] = {}
        for p in payloads:
            op = p.get("operator_applied") or "none"
            operator_counts[op] = operator_counts.get(op, 0) + 1

        feat_stats = FeatureStats(
            length_mean=float(np.mean(lengths)),
            length_std=float(np.std(lengths)),
            length_median=float(np.median(lengths)),
            length_min=int(np.min(lengths)),
            length_max=int(np.max(lengths)),
            category_counts=category_counts,
            provider_counts=provider_counts,
            operator_counts=operator_counts,
        )

        # --- 3. Supervised ML Model Training & Comparison ---
        # Feature Engineering: Combine PCA embedding components with structural syntactic features
        y = np.array(categories)
        
        # Structural syntactic features
        structural_features = []
        for p in payloads:
            txt = p.get("attack_text", "")
            structural_features.append([
                len(txt),
                1.0 if "{" in txt and "}" in txt else 0.0,  # JSON indicator
                1.0 if "<" in txt and ">" in txt else 0.0,  # XML/tag indicator
                1.0 if any(token in txt for token in ["[INST]", "###", "```"]) else 0.0,  # Delimiter indicator
                1.0 if "CANARY" in txt else 0.0,  # Explicit canary mention
            ])
        structural_features = np.array(structural_features, dtype=np.float32)

        # Standardize structural features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        norm_structural = scaler.fit_transform(structural_features)

        # Combine 5 PCA components + 5 structural features = 10 dense features
        pca_features = pca.transform(vectors)
        X_hybrid = np.hstack([pca_features, norm_structural])

        # Model 1: Regularized Logistic Regression on raw embeddings
        clf_lr = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs")

        # Model 2: Random Forest on Hybrid Features (semantic PCA + structural syntax)
        clf_rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)

        min_class_count = min(category_counts.values())
        k_folds = max(2, min(3, min_class_count))
        skf = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=42)

        cv_lr = cross_val_score(clf_lr, vectors, y, cv=skf, scoring="accuracy")
        cv_rf = cross_val_score(clf_rf, X_hybrid, y, cv=skf, scoring="accuracy")

        # Train final hybrid model for production scoring
        clf_rf.fit(X_hybrid, y)
        y_pred = clf_rf.predict(X_hybrid)
        report_dict = classification_report(y, y_pred, output_dict=True, zero_division=0)
        cm = confusion_matrix(y, y_pred, labels=unique_categories).tolist()

        model_perf = MLModelPerformance(
            model_name=f"RandomForest(Hybrid: 5-PCA + 5-Structural Features) [vs LogisticRegression CV: {float(np.mean(cv_lr))*100:.1f}%]",
            cv_mean_accuracy=float(np.mean(cv_rf)),
            cv_std_accuracy=float(np.std(cv_rf)),
            classes=unique_categories,
            classification_report=report_dict,
            confusion_matrix=cm,
        )

        return MLAnalysisReport(
            vector_stats=vec_stats,
            feature_stats=feat_stats,
            model_performance=model_perf,
        )
