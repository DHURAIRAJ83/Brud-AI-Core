"""Human-review aggregation and coverage-requirement helpers.

Reviews themselves are stored append-only by the repository layer — this
module only aggregates already-persisted review rows and decides which
outputs *require* a human review, never silently discarding disagreement.
"""

from __future__ import annotations

RUBRIC_VERSION = "phase13-rubric-v1"

VERDICTS = ("pass", "pass_with_warning", "fail", "needs_second_review")


def aggregate_reviews(reviews: list[dict]) -> dict:
    """Aggregate all reviews for one output (or a whole run). Disagreement is
    reported explicitly, never silently averaged away."""

    if not reviews:
        return {
            "review_count": 0, "average_overall_score": None, "verdicts": {},
            "disagreement": False,
        }
    overall_scores = [review["overall_score"] for review in reviews]
    verdict_counts: dict[str, int] = {}
    for review in reviews:
        verdict_counts[review["verdict"]] = verdict_counts.get(review["verdict"], 0) + 1
    distinct_verdicts = set(verdict_counts)
    disagreement = len(distinct_verdicts) > 1 or (max(overall_scores) - min(overall_scores) >= 2)
    return {
        "review_count": len(reviews),
        "average_overall_score": sum(overall_scores) / len(overall_scores),
        "verdicts": verdict_counts,
        "disagreement": disagreement,
    }


def aggregate_run_reviews(reviews_by_output: dict[str, list[dict]]) -> dict:
    all_reviews = [review for reviews in reviews_by_output.values() for review in reviews]
    if not all_reviews:
        return {
            "total_reviews": 0, "reviewed_output_count": 0, "average_overall_score": None,
            "disagreement_rate": None,
        }
    disagreements = 0
    for reviews in reviews_by_output.values():
        if aggregate_reviews(reviews)["disagreement"]:
            disagreements += 1
    reviewed_outputs = [output_id for output_id, reviews in reviews_by_output.items() if reviews]
    return {
        "total_reviews": len(all_reviews),
        "reviewed_output_count": len(reviewed_outputs),
        "average_overall_score": sum(r["overall_score"] for r in all_reviews) / len(all_reviews),
        "disagreement_rate": disagreements / len(reviewed_outputs) if reviewed_outputs else None,
    }


def required_review_output_ids(
    *,
    blocking_issue_output_ids: set[str],
    safety_failure_output_ids: set[str],
    one_sample_per_language_category_output_ids: set[str],
    borderline_candidate_output_ids: set[str],
) -> set[str]:
    """Union of every output that MUST receive a human review, per the spec:
    all blocking automated issues, all safety failures, at least one sample
    per language/category, and all candidate-selection borderline cases."""

    return (
        blocking_issue_output_ids
        | safety_failure_output_ids
        | one_sample_per_language_category_output_ids
        | borderline_candidate_output_ids
    )


def review_coverage(required_ids: set[str], reviewed_ids: set[str]) -> dict:
    if not required_ids:
        return {"coverage_ratio": 1.0, "missing_output_ids": []}
    missing = required_ids - reviewed_ids
    coverage = (len(required_ids) - len(missing)) / len(required_ids)
    return {"coverage_ratio": coverage, "missing_output_ids": sorted(missing)}
