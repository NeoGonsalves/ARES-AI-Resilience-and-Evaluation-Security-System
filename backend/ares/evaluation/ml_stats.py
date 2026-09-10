"""
Machine Learning Statistics & Attack Vector Modeling Engine for ARES.

Performs multivariate statistical analysis, clustering metrics, dimensionality
reduction (PCA), and trains an ML classification model on the 768-dim embeddings
stored in Qdrant Cloud.

Classifier: TF-IDF (word 1-2 grams + char 3-5 grams, 800 features)
            + 15-dim hand-crafted structural features
            -> LogisticRegression(C=5, class_weight='balanced', solver='lbfgs')
            Fast, interpretable, targets 95%+ on this domain.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

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
            f"(+-{self.vector_stats.pairwise_similarity_std:.4f})",
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
            f"(+-{self.model_performance.cv_std_accuracy * 100:.1f}%)",
            f"Classes Evaluated:      {self.model_performance.classes}",
            "=" * 60,
        ]
        return "\n".join(lines)


def _build_structural_features(payloads: List[Dict[str, Any]]) -> np.ndarray:
    """
    Extract hand-crafted structural/syntactic features from attack text payloads.
    These lexical signals complement TF-IDF and directly encode attack category patterns.
    """
    features = []
    for p in payloads:
        txt = p.get("attack_text", "")
        txt_lower = txt.lower()
        features.append([
            # Length signal
            len(txt),
            # Structural delimiters
            1.0 if "{" in txt and "}" in txt else 0.0,           # JSON braces
            1.0 if "<" in txt and ">" in txt else 0.0,           # XML / HTML tags
            1.0 if "```" in txt else 0.0,                        # Markdown code fence
            1.0 if "[INST]" in txt or "###" in txt else 0.0,     # Instruction markers
            1.0 if "<|im_start|>" in txt or "<|im_end|>" in txt else 0.0,  # ChatML tokens
            # Encoding indicators
            1.0 if any(x in txt_lower for x in ["base64", "decode", "hex", "rot13"]) else 0.0,
            1.0 if any(c in txt for c in "01234567890abcdef") and len(txt) > 40 else 0.0,  # Hex-like
            # Role-play indicators
            1.0 if any(x in txt_lower for x in ["pretend", "roleplay", "actor", "imagine", "dan", "omega", "jailbreak"]) else 0.0,
            # Instruction override indicators
            1.0 if any(x in txt_lower for x in ["ignore", "disregard", "override", "bypass", "forget previous"]) else 0.0,
            # Context smuggling indicators
            1.0 if any(x in txt_lower for x in ["retrieved", "knowledge base", "document excerpt", "log entry", "ticket", "email", "database"]) else 0.0,
            1.0 if any(x in txt_lower for x in ["previous conversation", "earlier session", "you told me", "my notes", "conversation history"]) else 0.0,
            # Canary / secret token references
            1.0 if "CANARY" in txt else 0.0,
            1.0 if "secret" in txt_lower or "token" in txt_lower else 0.0,
            # System / admin language
            1.0 if any(x in txt_lower for x in ["system", "admin", "root", "diagnostic", "audit", "emergency"]) else 0.0,
        ])
    return np.array(features, dtype=np.float32)


class AttackVectorMLAnalyzer:
    """
    Fetches raw vector embeddings and metadata from Qdrant Cloud, computes
    descriptive and multivariate statistics, and trains a supervised ML model.

    Classifier Pipeline:
        TF-IDF (char + word n-grams, 2000 features)
        + 15-dim Structural Features
        -> Soft-Voting Ensemble:
             * GradientBoostingClassifier (class_weight via sample_weight)
             * LogisticRegression(class_weight='balanced')
             * LinearSVC(class_weight='balanced') wrapped in CalibratedClassifierCV
    """

    def __init__(self, store: Optional[QdrantStore] = None, settings: Optional[Settings] = None):
        self.settings = settings or default_settings
        self.store = store or QdrantStore(settings=self.settings)

    def fetch_data(self, max_points: Optional[int] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Retrieve all vector points and metadata payloads from Qdrant with pagination."""
        all_points = []
        offset = None

        while True:
            batch_limit = 500
            if max_points is not None:
                remaining = max_points - len(all_points)
                if remaining <= 0:
                    break
                batch_limit = min(500, remaining)

            points, next_offset = self.store.client.scroll(
                collection_name=self.store.collection_name,
                with_vectors=True,
                with_payload=True,
                limit=batch_limit,
                offset=offset,
            )
            all_points.extend(points)

            if next_offset is None or (max_points is not None and len(all_points) >= max_points):
                break
            offset = next_offset

        if not all_points:
            raise ValueError(f"Collection '{self.store.collection_name}' is empty.")

        vectors = np.array([p.vector for p in all_points], dtype=np.float32)
        payloads = [p.payload or {} for p in all_points]
        return vectors, payloads

    def compute_analysis(self, max_points: Optional[int] = None) -> MLAnalysisReport:
        """Run full ML statistical pipeline and train classifier across the full corpus."""
        vectors, payloads = self.fetch_data(max_points=max_points)
        n_samples, n_dim = vectors.shape

        # --- 1. Vector Space & Pairwise Cosine Statistics ---
        # Sample up to 1000 points to avoid O(n^2) memory on large corpora
        sample_size = min(n_samples, 1000)
        sample_idx = np.random.choice(n_samples, sample_size, replace=False) if n_samples > 1000 else np.arange(n_samples)
        sim_sample = cosine_similarity(vectors[sample_idx])
        mask = ~np.eye(sample_size, dtype=bool)
        pairwise_sims = sim_sample[mask]

        # PCA Analysis
        n_components = min(5, n_samples)
        pca = PCA(n_components=n_components)
        pca.fit(vectors)
        top_3_variance = [float(v) for v in pca.explained_variance_ratio_[:3]]
        cum_variance_top_5 = float(np.sum(pca.explained_variance_ratio_))

        # Category labels
        categories = [p.get("category", "unknown") for p in payloads]
        unique_categories = sorted(list(set(categories)))

        # Silhouette score (sampled)
        sil_score = None
        if len(unique_categories) > 1 and len(unique_categories) < n_samples:
            try:
                sil_score = float(silhouette_score(vectors[sample_idx], [categories[i] for i in sample_idx], metric="cosine"))
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

        # --- 3. Feature Engineering ---
        texts = [p.get("attack_text", "") for p in payloads]
        y = np.array(categories)

        # 3a. TF-IDF: word n-grams (1,2) + char n-grams (3,5) → 800 features total
        tfidf_word = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            max_features=400,
            sublinear_tf=True,
            min_df=1,
        )
        tfidf_char = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=400,
            sublinear_tf=True,
            min_df=1,
        )
        X_word = tfidf_word.fit_transform(texts).toarray()
        X_char = tfidf_char.fit_transform(texts).toarray()

        # 3b. 15-dim structural/syntactic features
        struct_feats = _build_structural_features(payloads)
        scaler = StandardScaler()
        X_struct = scaler.fit_transform(struct_feats)

        # 3c. Concatenate: 400 + 400 + 15 = 815 features
        X = np.hstack([X_word, X_char, X_struct])

        # --- 4. Stratified K-Fold CV ---
        min_class_count = min(category_counts.values())
        k_folds = max(2, min(5, min_class_count))
        skf = StratifiedKFold(n_splits=k_folds, shuffle=True, random_state=42)

        # --- 5. Classifier: Balanced Logistic Regression on TF-IDF + Structural ---
        # Fast, interpretable, no threading overhead on Windows.
        # LR with class_weight='balanced' handles the context_smuggling imbalance.
        clf_lr = LogisticRegression(
            max_iter=2000,
            C=5.0,
            class_weight="balanced",
            solver="lbfgs",
        )

        # --- 6. Stratified 5-Fold Cross-Validation ---
        cv_scores = cross_val_score(clf_lr, X, y, cv=skf, scoring="accuracy")
        logger.info("LR CV: %.3f +- %.3f", np.mean(cv_scores), np.std(cv_scores))

        # Train on full corpus for the per-class classification report
        clf_lr.fit(X, y)
        y_pred      = clf_lr.predict(X)
        report_dict = classification_report(y, y_pred, output_dict=True, zero_division=0)
        cm          = confusion_matrix(y, y_pred, labels=unique_categories).tolist()

        model_name = (
            f"LogisticRegression(C=5, balanced) | "
            f"TF-IDF(word1-2+char3-5, 800feat) + 15-Structural | "
            f"CV={np.mean(cv_scores)*100:.1f}% (+-{np.std(cv_scores)*100:.1f}%)"
        )

        model_perf = MLModelPerformance(
            model_name=model_name,
            cv_mean_accuracy=float(np.mean(cv_scores)),
            cv_std_accuracy=float(np.std(cv_scores)),
            classes=unique_categories,
            classification_report=report_dict,
            confusion_matrix=cm,
        )

        return MLAnalysisReport(
            vector_stats=vec_stats,
            feature_stats=feat_stats,
            model_performance=model_perf,
        )
