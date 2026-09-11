"""Stats endpoint — serves the ML vector analysis report."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import APIRouter

from ares.api.schemas import CategoryAccuracy, StatsResponse

router = APIRouter(prefix="/api", tags=["stats"])

_REPORT_PATH = Path(__file__).parent.parent.parent.parent / "ml_vector_analysis_report.json"


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Load and return the ML vector analysis report."""
    if not _REPORT_PATH.exists():
        return StatsResponse(
            overall_accuracy=0.0, cv_accuracy=0.0, cv_std=0.0,
            corpus_size=0, category_counts={}, category_breakdown=[],
            model_name="Report not generated yet — run run_ml_statistics.py",
            generated_at=datetime.now(timezone.utc),
        )

    data = json.loads(_REPORT_PATH.read_text(encoding="utf-8"))

    model_perf: Dict = data.get("model_performance", {})
    cv_acc  = float(model_perf.get("cv_mean_accuracy", 0))
    cv_std  = float(model_perf.get("cv_std_accuracy", 0))
    cls_report: Dict = model_perf.get("classification_report", {})

    # Overall accuracy from classification report
    overall_acc = float(cls_report.get("accuracy", cv_acc))

    # Per-category breakdown
    skip_keys = {"accuracy", "macro avg", "weighted avg"}
    breakdown: list[CategoryAccuracy] = []
    for cat, vals in cls_report.items():
        if cat in skip_keys or not isinstance(vals, dict):
            continue
        breakdown.append(CategoryAccuracy(
            category=cat,
            precision=round(float(vals.get("precision", 0)), 4),
            recall=round(float(vals.get("recall", 0)), 4),
            f1_score=round(float(vals.get("f1-score", 0)), 4),
            support=int(vals.get("support", 0)),
        ))

    # Category counts from vector_stats
    vec_stats: Dict = data.get("vector_stats", {})
    category_counts: Dict[str, int] = vec_stats.get("category_distribution", {})
    corpus_size: int = vec_stats.get("total_vectors", sum(category_counts.values()))

    # Timestamp
    ts_str = data.get("generated_at", datetime.now(timezone.utc).isoformat())
    try:
        generated_at = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        generated_at = datetime.now(timezone.utc)

    return StatsResponse(
        overall_accuracy=round(overall_acc * 100, 2),
        cv_accuracy=round(cv_acc * 100, 2),
        cv_std=round(cv_std * 100, 2),
        corpus_size=corpus_size,
        category_counts=category_counts,
        category_breakdown=breakdown,
        model_name=model_perf.get("model_name", "LogisticRegression"),
        generated_at=generated_at,
    )
