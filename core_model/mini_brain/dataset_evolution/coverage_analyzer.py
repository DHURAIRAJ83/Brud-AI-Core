"""MB-11: Coverage Analyzer -- pure. Classifies five already-computed
dimensions (domain, language, difficulty, dataset type, knowledge
level) into Excellent / Good / Needs Expansion / Critical Gap, using
fixed, disclosed percentage thresholds. Never recomputes any
distribution itself -- every input is another phase's own real output.
"""

from __future__ import annotations

from typing import Any

EXCELLENT_THRESHOLD = 80.0
GOOD_THRESHOLD = 50.0
NEEDS_EXPANSION_THRESHOLD = 20.0


def _classify(percent: float) -> str:
    if percent >= EXCELLENT_THRESHOLD:
        return "Excellent"
    if percent >= GOOD_THRESHOLD:
        return "Good"
    if percent >= NEEDS_EXPANSION_THRESHOLD:
        return "Needs Expansion"
    return "Critical Gap"


def analyze_coverage_summary(
    *,
    domain_coverage: dict[str, Any],
    language_distribution_percentages: dict[str, float],
    difficulty_distribution: dict[str, int],
    record_type_counts: dict[str, int],
    curriculum_verdict_counts: dict[str, int],
) -> dict[str, Any]:
    by_domain = {
        domain: {"coverage_percent": data["coverage_percent"], "classification": _classify(data["coverage_percent"])}
        for domain, data in domain_coverage.items()
    }

    by_language = {
        language: {"percent": percent, "classification": _classify(percent)}
        for language, percent in language_distribution_percentages.items()
    }

    difficulty_total = sum(difficulty_distribution.values())
    balanced_percent = (
        round(min(difficulty_distribution.get("Medium", 0), difficulty_distribution.get("Hard", 0)) / difficulty_total * 100 * 2, 1)
        if difficulty_total else 0.0
    )
    by_difficulty = {
        "distribution": difficulty_distribution,
        "balance_percent": min(balanced_percent, 100.0),
        "classification": _classify(min(balanced_percent, 100.0)),
    }

    type_total = sum(record_type_counts.values())
    type_diversity_percent = round(len(record_type_counts) / 5 * 100, 1) if type_total else 0.0
    by_dataset_type = {
        "counts": record_type_counts,
        "diversity_percent": min(type_diversity_percent, 100.0),
        "classification": _classify(min(type_diversity_percent, 100.0)),
    }

    curriculum_total = sum(curriculum_verdict_counts.values())
    good_sequence_percent = (
        round(curriculum_verdict_counts.get("Good Sequence", 0) / curriculum_total * 100, 1) if curriculum_total else 0.0
    )
    by_knowledge_level = {
        "verdict_counts": curriculum_verdict_counts,
        "good_sequence_percent": good_sequence_percent,
        "classification": _classify(good_sequence_percent),
    }

    all_classifications = (
        [v["classification"] for v in by_domain.values()]
        + [v["classification"] for v in by_language.values()]
        + [by_difficulty["classification"], by_dataset_type["classification"], by_knowledge_level["classification"]]
    )
    critical_gap_count = sum(1 for c in all_classifications if c == "Critical Gap")
    needs_expansion_count = sum(1 for c in all_classifications if c == "Needs Expansion")

    return {
        "by_domain": by_domain,
        "by_language": by_language,
        "by_difficulty": by_difficulty,
        "by_dataset_type": by_dataset_type,
        "by_knowledge_level": by_knowledge_level,
        "critical_gap_count": critical_gap_count,
        "needs_expansion_count": needs_expansion_count,
        "dimensions_evaluated": len(all_classifications),
    }
