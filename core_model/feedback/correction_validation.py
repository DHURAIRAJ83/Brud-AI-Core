"""Corrected-response validation.

A corrected response is a proposed replacement, never an in-place
rewrite of the original output. Validation only ever produces a
status and an issue list attached to the correction's own row; it
never touches ``feedback_subjects.output_checksum_sha256`` (the
original output's immutable record).
"""

from __future__ import annotations

from typing import Any

from core_model.feedback.privacy_filter import assess_feedback_privacy
from core_model.feedback.safety_filter import assess_correction_safety
from core_model.instruction_tuning.evaluation import bounded_length, valid_unicode
from core_model.rag.language_routing import classify_language

MAXIMUM_CORRECTION_CHARACTERS_DEFAULT = 4000


def validate_correction(
    *,
    corrected_text: str,
    requested_language: str | None,
    system_text: str | None,
    original_prompt_text: str | None,
    citation_ids: list[str],
    accessible_citation_ids: set[str],
    maximum_characters: int = MAXIMUM_CORRECTION_CHARACTERS_DEFAULT,
    regression_fixture_checksums: frozenset[str] = frozenset(),
    training_contamination_checksums: frozenset[str] = frozenset(),
    correction_checksum: str | None = None,
) -> dict[str, Any]:
    """Returns ``{"status": ..., "issues": [...], "detected_language": ...}``.

    ``status`` is one of ``validated`` / ``validated_with_warnings`` /
    ``rejected`` -- never a silent pass over a real problem."""

    issues: list[str] = []

    if not corrected_text.strip():
        issues.append("empty_content")

    unicode_result = valid_unicode(corrected_text)
    if unicode_result["status"] != "pass":
        issues.append("invalid_unicode")

    length_result = bounded_length(corrected_text, max_chars=maximum_characters)
    if length_result["status"] != "pass":
        issues.append("response_length_exceeds_policy")

    privacy = assess_feedback_privacy(corrected_text)
    if privacy["status"] == "blocked":
        issues.append("secret_or_sensitive_content")
    elif privacy["status"] == "requires_review":
        issues.append("privacy_requires_review")

    safety = assess_correction_safety(
        corrected_text, system_text=system_text, original_prompt_text=original_prompt_text
    )
    if safety["status"] == "blocked":
        issues.append("unsafe_instruction_content")
    if "prompt_leakage" in safety["matched_categories"]:
        issues.append("prompt_or_system_leakage")
    if "role_token_leakage" in safety["matched_categories"]:
        issues.append("role_token_leakage")
    if "repetition" in safety["matched_categories"]:
        issues.append("excessive_repetition")

    language_info = classify_language(corrected_text)
    detected_language = language_info["language_category"]
    if requested_language and requested_language not in {"unknown", "auto"}:
        if detected_language not in {requested_language, "mixed"}:
            issues.append("language_mismatch")

    unknown_citations = sorted(set(citation_ids) - accessible_citation_ids)
    if unknown_citations:
        issues.append("citation_ids_unresolved")

    if correction_checksum and correction_checksum in regression_fixture_checksums:
        issues.append("regression_fixture_leakage")
    if correction_checksum and correction_checksum in training_contamination_checksums:
        issues.append("training_test_contamination")

    blocking = {
        "empty_content",
        "invalid_unicode",
        "secret_or_sensitive_content",
        "unsafe_instruction_content",
        "prompt_or_system_leakage",
        "role_token_leakage",
        "citation_ids_unresolved",
        "regression_fixture_leakage",
        "training_test_contamination",
    }
    if blocking & set(issues):
        status = "rejected"
    elif issues:
        status = "validated_with_warnings"
    else:
        status = "validated"

    return {
        "status": status,
        "issues": issues,
        "detected_language": detected_language,
        "unknown_citation_ids": unknown_citations,
    }
