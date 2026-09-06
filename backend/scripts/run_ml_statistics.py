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


if __name__ == "__main__":
    main()
