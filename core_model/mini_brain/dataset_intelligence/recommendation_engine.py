"""MB-05: Recommendation Engine -- rule-based, deterministic
recommendations, each carrying an explicit WHY. Never executes
anything -- purely advisory text built from the other analyzers'
already-computed results.
"""

from __future__ import annotations

from typing import Any

SMALL_DATASET_THRESHOLD = 50
LARGE_DATASET_THRESHOLD = 5000
MIN_METADATA_KEYS_FOR_GOOD_DOCUMENTATION = 3


def _rec(*, category: str, recommendation: str, reason: str, priority: str) -> dict[str, Any]:
    return {"category": category, "recommendation": recommendation, "reason": reason, "priority": priority}


def generate_recommendations(
    *, dataset: dict[str, Any], quality: dict[str, Any], language: dict[str, Any],
    duplicates: dict[str, Any], domain: dict[str, Any], training: dict[str, Any],
    rag: dict[str, Any], sft: dict[str, Any],
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    total = dataset["record_count"]

    if quality.get("flagged_records"):
        top_issues = sorted(quality["issue_counts"].items(), key=lambda kv: -kv[1])[:3]
        recommendations.append(_rec(
            category="cleaning",
            recommendation=f"Review and clean {quality['flagged_records']} flagged record(s) before use.",
            reason=f"most common issues: {', '.join(f'{name} ({count})' for name, count in top_issues)}",
            priority="high" if quality["clean_ratio"] < 0.5 else "medium",
        ))

    if duplicates["duplicate_record_count"] > 0:
        recommendations.append(_rec(
            category="cleaning",
            recommendation=f"Remove or merge {duplicates['duplicate_record_count']} exact-duplicate record(s).",
            reason=f"{len(duplicates['duplicate_record_groups'])} duplicate group(s) found by exact content-hash match",
            priority="medium",
        ))

    if total and total < SMALL_DATASET_THRESHOLD:
        recommendations.append(_rec(
            category="merging",
            recommendation="Consider merging this source with another compatible dataset before training.",
            reason=f"only {total} records -- below the {SMALL_DATASET_THRESHOLD}-record practical minimum",
            priority="medium",
        ))
    elif total and total > LARGE_DATASET_THRESHOLD and len(dataset.get("by_record_type", {})) > 2:
        recommendations.append(_rec(
            category="splitting",
            recommendation="Consider splitting this source by record_type for clearer training/RAG/SFT separation.",
            reason=f"{total} records span {len(dataset['by_record_type'])} record types",
            priority="low",
        ))

    metadata_key_count = len(dataset.get("metadata_keys_observed", []))
    if metadata_key_count < MIN_METADATA_KEYS_FOR_GOOD_DOCUMENTATION:
        recommendations.append(_rec(
            category="documentation",
            recommendation="Add more descriptive metadata (e.g., topic, difficulty, source reference).",
            reason=f"only {metadata_key_count} distinct metadata key(s) observed across all records",
            priority="low",
        ))

    empty_count = quality.get("empty_content_records", 0)
    if empty_count > 0:
        recommendations.append(_rec(
            category="metadata improvements",
            recommendation=f"Fill in or remove {empty_count} record(s) with no content at all.",
            reason="empty records provide no training/RAG/SFT value and dilute quality metrics",
            priority="high",
        ))

    if total and language.get("declared_language_mismatches", 0) / total > 0.1:
        recommendations.append(_rec(
            category="language balancing",
            recommendation="Review records whose declared language does not match the detected language.",
            reason=f"{language['declared_language_mismatches']} of {total} records mismatch",
            priority="medium",
        ))

    if training["status"] != "Ready":
        recommendations.append(_rec(
            category="training suitability",
            recommendation=f"Address the following before training: {'; '.join(training['reasons'])}",
            reason=f"Training Readiness verdict: {training['status']}",
            priority="high" if training["status"] == "Not Ready" else "medium",
        ))

    if rag["status"] != "Ready":
        recommendations.append(_rec(
            category="RAG suitability",
            recommendation=f"Address the following before RAG ingestion: {'; '.join(rag['reasons'])}",
            reason=f"RAG Readiness verdict: {rag['status']}",
            priority="high" if rag["status"] == "Not Ready" else "medium",
        ))

    if sft["status"] != "Ready":
        recommendations.append(_rec(
            category="SFT suitability",
            recommendation=f"Address the following before SFT use: {'; '.join(sft['reasons'])}",
            reason=f"SFT Readiness verdict: {sft['status']}",
            priority="high" if sft["status"] == "Not Ready" else "medium",
        ))

    return recommendations
