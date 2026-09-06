"""
Run ML Statistics & Vector Space Modeling Script for ARES.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from ares.evaluation.ml_stats import AttackVectorMLAnalyzer


def main():
    print("Fetching 768-dim attack vectors from Qdrant Cloud...")
    analyzer = AttackVectorMLAnalyzer()
    report = analyzer.compute_analysis()

    print("\n" + report.summary() + "\n")

    # Detailed Category Classification Breakdown
    print("--- DETAILED CATEGORY CLASSIFICATION BREAKDOWN ---")
    rep_dict = report.model_performance.classification_report
    print(f"{'Category':<24} | {'Precision':<10} | {'Recall':<8} | {'F1-Score':<8} | {'Support':<8}")
    print("-" * 65)
    for cls_name in report.model_performance.classes:
        metrics = rep_dict.get(cls_name, {})
        print(
            f"{cls_name:<24} | "
            f"{metrics.get('precision', 0.0):<10.2f} | "
            f"{metrics.get('recall', 0.0):<8.2f} | "
            f"{metrics.get('f1-score', 0.0):<8.2f} | "
            f"{int(metrics.get('support', 0)):<8}"
        )
    print("-" * 65)
    print(f"Overall Accuracy: {rep_dict.get('accuracy', 0.0) * 100:.1f}%")
    print("Confusion Matrix:")
    for row in report.model_performance.confusion_matrix:
        print(" ", row)

    # Save serialized report
    import json
    out_path = backend_dir / "ml_vector_analysis_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "sample_count": report.vector_stats.sample_count,
                "vector_dim": report.vector_stats.vector_dim,
                "pairwise_similarity_mean": report.vector_stats.pairwise_similarity_mean,
                "pairwise_similarity_std": report.vector_stats.pairwise_similarity_std,
                "pca_top_3_variance": report.vector_stats.pca_top_3_variance,
                "pca_cumulative_variance_top_5": report.vector_stats.pca_cumulative_variance_top_5,
                "silhouette_score": report.vector_stats.silhouette_score,
                "category_counts": report.feature_stats.category_counts,
                "classifier_name": report.model_performance.model_name,
                "cv_mean_accuracy": report.model_performance.cv_mean_accuracy,
                "cv_std_accuracy": report.model_performance.cv_std_accuracy,
                "classification_report": report.model_performance.classification_report,
                "confusion_matrix": report.model_performance.confusion_matrix,
            },
            f,
            indent=2,
        )
    print(f"\n[OK] ML Vector Analysis Report saved to: {out_path}")


if __name__ == "__main__":
    main()
