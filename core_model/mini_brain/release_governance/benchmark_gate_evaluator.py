"""MB-20: Benchmark Gate Evaluator -- pure. Consumes MB-19's own
already-computed benchmark result rows (never re-benchmarks anything)
and classifies each known metric against a fixed pass/marginal/fail
band. A metric with no defined band (e.g. a coverage ratio that
legitimately varies by dataset content) is reported as
`"informational"` and never counted toward pass/fail -- this avoids
falsely blocking a release over a metric that has no universally
"correct" value.
"""

from __future__ import annotations

from typing import Any

# metric_name -> (pass_at_or_above, marginal_at_or_above) -- higher is better
HIGHER_IS_BETTER = {
    "unicode_integrity": (90.0, 70.0),
    "tamil_character_validity": (90.0, 70.0),
    "citation_validity_rate": (0.8, 0.5),
    "evidence_coverage_rate": (0.5, 0.25),
    "topk_evidence_availability": (0.8, 0.5),
    "average_relevance_score": (0.5, 0.3),
    "manifest_checksum_validity_rate": (1.0, 0.99),
    "artifact_count_consistency_rate": (1.0, 0.99),
}

# metric_name -> (pass_at_or_below, marginal_at_or_below) -- lower is better
LOWER_IS_BETTER = {
    "ocr_conflict_ratio": (0.1, 0.3),
    "unsupported_sentence_ratio": (0.2, 0.4),
    "insufficient_evidence_rate": (0.1, 0.3),
    "missing_file_count": (0, 0),
}


def _classify(metric_name: str, value: float) -> str | None:
    if metric_name in HIGHER_IS_BETTER:
        pass_at, marginal_at = HIGHER_IS_BETTER[metric_name]
        if value >= pass_at:
            return "passed"
        if value >= marginal_at:
            return "marginal"
        return "failed"
    if metric_name in LOWER_IS_BETTER:
        pass_at, marginal_at = LOWER_IS_BETTER[metric_name]
        if value <= pass_at:
            return "passed"
        if value <= marginal_at:
            return "marginal"
        return "failed"
    return None


def run_benchmark_gates(*, benchmark_results: list[dict[str, Any]]) -> dict[str, Any]:
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    marginal: list[dict[str, Any]] = []
    informational: list[dict[str, Any]] = []

    for result in benchmark_results:
        metric_name = result["metric_name"]
        value = result["metric_value"]
        if value is None:
            continue
        classification = _classify(metric_name, value)
        entry = {"category": result["category"], "metric_name": metric_name, "value": value}
        if classification == "passed":
            passed.append(entry)
        elif classification == "marginal":
            marginal.append(entry)
        elif classification == "failed":
            failed.append(entry)
        else:
            informational.append(entry)

    if failed:
        overall_status = "fail"
    elif marginal:
        overall_status = "marginal"
    elif passed:
        overall_status = "pass"
    else:
        overall_status = "no_data"

    return {
        "passed_metrics": passed, "failed_metrics": failed, "marginal_metrics": marginal,
        "informational_metrics": informational, "overall_benchmark_status": overall_status,
        "evaluated_metric_count": len(passed) + len(failed) + len(marginal),
        "disclosure": (
            "only metrics with a defined pass/marginal/fail band are counted toward the overall "
            "status -- coverage-style metrics that legitimately vary by dataset content are reported "
            "as informational only, never scored"
        ),
    }
