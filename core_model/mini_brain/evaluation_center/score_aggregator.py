"""MB-19: Score Aggregator -- pure. Combines every benchmark
category's own score into one overall figure. A missing category
(honestly unavailable, e.g. no RAG session collected) is excluded from
the average entirely, never silently scored as zero.
"""

from __future__ import annotations

from typing import Any


def aggregate_scores(*, category_scores: dict[str, float | None]) -> dict[str, Any]:
    available = {name: value for name, value in category_scores.items() if value is not None}
    overall = round(sum(available.values()) / len(available), 1) if available else None

    return {
        "category_scores": category_scores,
        "categories_scored": len(available),
        "categories_total": len(category_scores),
        "overall_score": overall,
        "formula": "unweighted mean of available category scores -- a missing category is excluded, never scored as zero",
    }
