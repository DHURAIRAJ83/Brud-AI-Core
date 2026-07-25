"""Dataset-candidate contamination checks.

A candidate must never silently enter a dataset version that shares
content with anything used to measure that model: the training split,
the validation split, the test split, any evaluation fixture set
(Phase 13 model evaluation, Phase 16 RAG evaluation, Phase 17 memory
evaluation), or a feedback regression fixture. Blocking checks fail
approval outright rather than merely warning.
"""

from __future__ import annotations

from typing import Any

from core_model.feedback import BLOCKING_CONTAMINATION_STATUSES
from core_model.feedback.deduplication import checksum_of, normalize_for_comparison


def _matches_any(checksum: str, reference_checksums: frozenset[str]) -> bool:
    return checksum in reference_checksums


def check_contamination(
    *,
    prompt_text: str,
    output_text: str,
    training_checksums: frozenset[str] = frozenset(),
    validation_checksums: frozenset[str] = frozenset(),
    test_checksums: frozenset[str] = frozenset(),
    evaluation_fixture_checksums: frozenset[str] = frozenset(),
    regression_fixture_checksums: frozenset[str] = frozenset(),
    subject_output_checksum: str | None = None,
    hidden_system_prompt_checksum: str | None = None,
) -> dict[str, Any]:
    """Returns the single most severe contamination status found, plus
    the full list of every issue code detected (never just the first
    match) so review evidence is complete."""

    combined_checksum = checksum_of(
        normalize_for_comparison(f"{prompt_text}\n{output_text}")
    )
    output_checksum = checksum_of(normalize_for_comparison(output_text))
    prompt_checksum = checksum_of(normalize_for_comparison(prompt_text))

    issues: list[str] = []
    if _matches_any(combined_checksum, test_checksums):
        issues.append("test_leakage")
    if _matches_any(combined_checksum, evaluation_fixture_checksums):
        issues.append("evaluation_fixture_leakage")
    if _matches_any(combined_checksum, regression_fixture_checksums):
        issues.append("regression_fixture_leakage")
    if _matches_any(combined_checksum, validation_checksums):
        issues.append("validation_leakage")
    if _matches_any(combined_checksum, training_checksums):
        issues.append("training_duplicate")
    if subject_output_checksum and output_checksum == subject_output_checksum:
        issues.append("subject_output_copy")
    if hidden_system_prompt_checksum and (
        prompt_checksum == hidden_system_prompt_checksum
        or output_checksum == hidden_system_prompt_checksum
    ):
        issues.append("hidden_prompt_leakage")

    blocking = [issue for issue in issues if issue in BLOCKING_CONTAMINATION_STATUSES]
    if blocking:
        status = blocking[0]
    elif issues:
        status = issues[0]
    else:
        status = "clean"

    return {"status": status, "issues": issues, "blocks_approval": bool(blocking)}
