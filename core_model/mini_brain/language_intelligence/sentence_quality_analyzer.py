"""MB-13: Sentence Quality Analyzer -- pure. Reuses `core_model.
mini_brain.quality.tamil_fluency_validator.validate_tamil_fluency()`
unchanged for fragment and word-repetition detection. Duplicate
sentences are already detected at the service layer by the existing
`ExternalDatasetDuplicateService` (Phase 12, reused unchanged exactly
as MB-09/MB-10/MB-11 already do) -- this module only classifies the
already-detected groups, never re-scans for duplicates itself.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.quality.tamil_fluency_validator import validate_tamil_fluency


def analyze_sentence_quality(*, texts: list[str], duplicate_groups: list[list[str]]) -> dict[str, Any]:
    total = len(texts)
    fragment_count = 0
    repetition_count = 0
    word_counts: list[int] = []

    for text in texts:
        result = validate_tamil_fluency(text)
        if "fragment_only_answer" in result["issues"]:
            fragment_count += 1
        if any(issue.startswith("word_repetition") for issue in result["issues"]):
            repetition_count += 1
        word_counts.append(result["word_count"])

    average_word_count = round(sum(word_counts) / total, 1) if total else 0.0
    duplicate_record_count = sum(len(group) for group in duplicate_groups)

    issue_rate = ((fragment_count + repetition_count) / total) if total else 0.0
    duplicate_rate = (duplicate_record_count / total) if total else 0.0
    naturalness_score = round(max(0.0, 100.0 - issue_rate * 60.0 - duplicate_rate * 40.0), 1)

    return {
        "records_analyzed": total,
        "fragment_count": fragment_count,
        "repetition_count": repetition_count,
        "average_word_count": average_word_count,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_record_count": duplicate_record_count,
        "naturalness_score": naturalness_score,
    }
