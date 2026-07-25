"""Dataset-candidate construction from reviewed, corrected feedback.

A candidate may only be built once every precondition holds: a
completed human review recommending it, a validated (not rejected)
corrected response, and privacy/safety scans that did not block. This
module only assembles the candidate payload deterministically -- the
service layer is responsible for actually checking those preconditions
before calling it.
"""

from __future__ import annotations

from typing import Any

from core_model.feedback.deduplication import checksum_of
from core_model.rag.text_normalization import content_checksum


def preconditions_met(
    *,
    review_verdict: str | None,
    correction_validation_status: str | None,
    privacy_status: str,
    safety_status: str,
) -> tuple[bool, str | None]:
    if review_verdict is None:
        return False, "missing_human_review"
    if review_verdict not in {"valid_feedback", "partially_valid", "candidate_recommended"}:
        return False, "review_did_not_recommend_candidate"
    if correction_validation_status is None:
        return False, "missing_validated_correction"
    if correction_validation_status == "rejected":
        return False, "correction_rejected"
    if privacy_status == "blocked":
        return False, "privacy_blocked"
    if safety_status == "blocked":
        return False, "safety_blocked"
    return True, None


def build_candidate_version(
    *,
    prompt_text: str,
    input_text: str | None,
    output_text: str,
    language: str,
    change_reason: str,
) -> dict[str, Any]:
    prompt_checksum = content_checksum(prompt_text)
    output_checksum = content_checksum(output_text)
    metadata_checksum = checksum_of(f"{language}|{change_reason}")
    return {
        "prompt_text": prompt_text,
        "input_text": input_text,
        "output_text": output_text,
        "language": language,
        "prompt_checksum_sha256": prompt_checksum,
        "output_checksum_sha256": output_checksum,
        "metadata_checksum_sha256": metadata_checksum,
        "change_reason": change_reason,
    }


def infer_candidate_type(
    *, subject_type: str, feedback_type: str, is_preference_pair: bool
) -> str:
    """Deterministic, documented mapping -- never a guessed/ML-inferred type."""

    if is_preference_pair:
        return "preference"
    if feedback_type in {"citation_report", "retrieval_report"}:
        return "instruction"
    if subject_type == "conversation_response":
        return "chat"
    if subject_type == "memory_orchestration_response":
        return "chat"
    if subject_type == "rag_grounded_answer":
        return "instruction"
    if feedback_type == "safety_report":
        return "safety"
    return "instruction"
