"""MB-06: Model Comparator -- pure. Compares two sets of already-run
benchmark metrics (previous production model vs newly trained model)
and classifies each `(language, category, metric_name)` triple as
Improvement / Regression / Neutral.

Honest scope: the existing `ModelEvaluationService` records metrics
under whatever `language`/`category` an admin defined when the
fixture set was created -- there is no fixed, guaranteed "Tamil,
English, Reasoning, Coding, Mathematics, Science, Memory, Safety,
Latency" enum anywhere in the existing system. This module compares
whatever categories are ACTUALLY present in both metric sets; a
category named in the task but absent from both runs' real fixtures
is reported as `no_data`, never fabricated.
"""

from __future__ import annotations

from typing import Any

REGRESSION_THRESHOLD = 0.02  # 2% relative change
# Metrics where a LOWER value is better -- everything else assumes higher is better.
LOWER_IS_BETTER_METRIC_NAMES = frozenset({"latency", "latency_ms", "loss", "perplexity", "error_rate"})

REQUESTED_CATEGORIES = (
    "tamil", "english", "reasoning", "coding", "mathematics", "science", "memory", "safety", "latency",
)


def _metric_key(metric: dict[str, Any]) -> tuple[str, str, str]:
    return (metric.get("language") or "unspecified", metric.get("category") or "unspecified", metric["metric_name"])


def _index_metrics(metrics: list[dict[str, Any]]) -> dict[tuple[str, str, str], float | None]:
    return {_metric_key(m): m.get("metric_value") for m in metrics}


def compare_models(
    *, previous_metrics: list[dict[str, Any]], new_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    previous_index = _index_metrics(previous_metrics)
    new_index = _index_metrics(new_metrics)
    all_keys = sorted(set(previous_index) | set(new_index))

    comparisons: list[dict[str, Any]] = []
    for key in all_keys:
        language, category, metric_name = key
        previous_value = previous_index.get(key)
        new_value = new_index.get(key)

        if previous_value is None or new_value is None:
            comparisons.append({
                "language": language, "category": category, "metric_name": metric_name,
                "previous_value": previous_value, "new_value": new_value,
                "classification": "no_data", "reason": "metric missing from one or both runs",
            })
            continue

        lower_is_better = metric_name.lower() in LOWER_IS_BETTER_METRIC_NAMES
        if previous_value == 0:
            relative_change = 0.0 if new_value == 0 else float("inf")
        else:
            relative_change = (new_value - previous_value) / abs(previous_value)
        effective_change = -relative_change if lower_is_better else relative_change

        if effective_change > REGRESSION_THRESHOLD:
            classification = "improvement"
        elif effective_change < -REGRESSION_THRESHOLD:
            classification = "regression"
        else:
            classification = "neutral"

        comparisons.append({
            "language": language, "category": category, "metric_name": metric_name,
            "previous_value": previous_value, "new_value": new_value,
            "relative_change": round(relative_change, 4) if relative_change != float("inf") else None,
            "classification": classification,
            "reason": f"{round(relative_change * 100, 1)}% relative change, {REGRESSION_THRESHOLD * 100:.0f}% threshold",
        })

    present_categories = {c["category"] for c in comparisons if c["classification"] != "no_data"}
    missing_requested_categories = [cat for cat in REQUESTED_CATEGORIES if cat not in present_categories]

    return {
        "comparisons": comparisons,
        "improvement_count": sum(1 for c in comparisons if c["classification"] == "improvement"),
        "regression_count": sum(1 for c in comparisons if c["classification"] == "regression"),
        "neutral_count": sum(1 for c in comparisons if c["classification"] == "neutral"),
        "no_data_count": sum(1 for c in comparisons if c["classification"] == "no_data"),
        "requested_categories_without_real_data": missing_requested_categories,
    }
