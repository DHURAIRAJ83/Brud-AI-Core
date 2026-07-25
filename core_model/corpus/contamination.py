"""Corpus contamination detection against training/validation/test
splits and every existing evaluation/regression/holdout fixture set.

Mirrors Phase 18's ``core_model.feedback.contamination`` checksum-set
comparison approach (never a heavyweight cross-index search) but scoped
to this phase's own normalized-checksum variants. Blocking issues
always prevent training export outright; a training-split duplicate
alone is not blocking (it may be deduplicated or linked instead).
"""

from __future__ import annotations

from typing import Any

from core_model.corpus import BLOCKING_CONTAMINATION_ISSUES
from core_model.corpus.exact_deduplication import tamil_safe_normalized_checksum


def check_contamination(
    *,
    segment_text: str,
    training_checksums: frozenset[str] = frozenset(),
    validation_checksums: frozenset[str] = frozenset(),
    test_checksums: frozenset[str] = frozenset(),
    evaluation_fixture_checksums: frozenset[str] = frozenset(),
    regression_fixture_checksums: frozenset[str] = frozenset(),
    holdout_checksums: frozenset[str] = frozenset(),
    hidden_prompt_checksums: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Returns every issue found (never just the first) plus whether
    any of them blocks training export."""

    checksum = tamil_safe_normalized_checksum(segment_text)
    issues: list[str] = []

    if checksum in test_checksums:
        issues.append("test_leakage")
    if checksum in evaluation_fixture_checksums:
        issues.append("evaluation_fixture_leakage")
    if checksum in regression_fixture_checksums:
        issues.append("regression_fixture_leakage")
    if checksum in validation_checksums:
        issues.append("validation_leakage")
    if checksum in holdout_checksums:
        issues.append("holdout_leakage")
    if checksum in hidden_prompt_checksums:
        issues.append("hidden_prompt_leakage")
    if checksum in training_checksums:
        issues.append("training_duplicate")

    blocking = [issue for issue in issues if issue in BLOCKING_CONTAMINATION_ISSUES]
    return {
        "checksum": checksum,
        "issues": issues,
        "blocks_training": bool(blocking),
        "blocking_issues": blocking,
    }
