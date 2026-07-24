"""Release-candidate eligibility assessment.

This is release eligibility, never production-deployment approval. The
cascade is blocking-first, exactly like Phase 13's chat-readiness gate
(``core_model.model_evaluation.readiness_gates.assess_chat_readiness``):
any blocking reason forces ``blocked`` regardless of other scores; only
zero blocking and zero warnings yields ``eligible``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ELIGIBLE = "eligible"
ELIGIBLE_WITH_WARNINGS = "eligible_with_warnings"
BLOCKED = "blocked"
NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True)
class EligibilityThresholds:
    require_evaluation: bool = True
    allow_warning_eligibility: bool = True
    require_licence: bool = True
    require_model_card: bool = True
    require_evaluation_manifest: bool = True
    require_instruction_manifest: bool = True
    require_base_training_manifest: bool = True
    require_rollback_target: bool = False


def assess_release_eligibility(
    *,
    checkpoint_missing: bool,
    checkpoint_corrupt: bool,
    model_config_missing: bool,
    tokenizer_missing: bool,
    tokenizer_vocab_mismatch: bool,
    checksum_mismatch_count: int,
    lineage_complete: bool,
    instruction_tuned: bool,
    evaluation_status: str | None,
    evaluation_manifest_present: bool,
    instruction_manifest_present: bool,
    base_training_manifest_present: bool,
    safety_blocking_issue: bool,
    licence_status: str,
    model_card_status: str,
    manifest_mismatch: bool,
    candidate_already_retired_or_archived: bool,
    rollback_target_available: bool,
    dataset_scale_warning: bool,
    human_review_partial: bool,
    resource_requirement_unknown: bool,
    thresholds: EligibilityThresholds,
) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []

    if checkpoint_missing:
        reasons.append("checkpoint_missing")
    if checkpoint_corrupt:
        reasons.append("checkpoint_corrupt")
    if model_config_missing:
        reasons.append("model_config_missing")
    if tokenizer_missing:
        reasons.append("tokenizer_missing")
    if tokenizer_vocab_mismatch:
        reasons.append("tokenizer_vocab_mismatch")
    if checksum_mismatch_count > 0:
        reasons.append("artifact_checksum_mismatch")
    if not lineage_complete:
        reasons.append("dataset_lineage_missing")
    if thresholds.require_evaluation and evaluation_status == "evaluation_blocked":
        reasons.append("evaluation_blocked")
    if thresholds.require_evaluation and evaluation_status is None:
        reasons.append("evaluation_manifest_missing")
    if thresholds.require_evaluation_manifest and not evaluation_manifest_present:
        reasons.append("evaluation_manifest_missing")
    if (
        instruction_tuned
        and thresholds.require_instruction_manifest
        and not instruction_manifest_present
    ):
        reasons.append("instruction_manifest_missing")
    if thresholds.require_base_training_manifest and not base_training_manifest_present:
        reasons.append("training_manifest_missing")
    if safety_blocking_issue:
        reasons.append("safety_blocking_issue")
    if thresholds.require_licence and licence_status in {"missing", "unsupported"}:
        reasons.append(
            "licence_missing" if licence_status == "missing" else "licence_unsupported"
        )
    if thresholds.require_model_card and model_card_status in {"missing", "invalid"}:
        reasons.append("model_card_incomplete")
    if manifest_mismatch:
        reasons.append("release_manifest_mismatch")
    if candidate_already_retired_or_archived:
        reasons.append("candidate_already_retired_or_archived")
    if thresholds.require_rollback_target and not rollback_target_available:
        reasons.append("rollback_target_unavailable")

    if evaluation_status == "evaluation_warning":
        warnings.append("evaluation_warning")
    if dataset_scale_warning:
        warnings.append("limited_training_dataset")
    if human_review_partial:
        warnings.append("partial_human_review")
    if resource_requirement_unknown:
        warnings.append("resource_estimate_warning")
    if model_card_status == "not_validated":
        warnings.append("model_card_not_yet_validated")

    if reasons:
        status = BLOCKED
    elif warnings and not thresholds.allow_warning_eligibility:
        status = BLOCKED
    elif warnings:
        status = ELIGIBLE_WITH_WARNINGS
    else:
        status = ELIGIBLE

    dimension_scores = _dimension_scores(
        checkpoint_missing=checkpoint_missing, checkpoint_corrupt=checkpoint_corrupt,
        model_config_missing=model_config_missing, tokenizer_missing=tokenizer_missing,
        tokenizer_vocab_mismatch=tokenizer_vocab_mismatch,
        checksum_mismatch_count=checksum_mismatch_count, lineage_complete=lineage_complete,
        instruction_tuned=instruction_tuned, evaluation_status=evaluation_status,
        base_training_manifest_present=base_training_manifest_present,
        safety_blocking_issue=safety_blocking_issue, licence_status=licence_status,
        model_card_status=model_card_status, manifest_mismatch=manifest_mismatch,
        resource_requirement_unknown=resource_requirement_unknown,
        rollback_target_available=rollback_target_available,
    )
    return {
        "status": status,
        "dimension_scores": dimension_scores,
        "rationale": {"blocking_reasons": reasons, "warnings": warnings},
    }


def _dimension_scores(
    *, checkpoint_missing: bool, checkpoint_corrupt: bool, model_config_missing: bool,
    tokenizer_missing: bool, tokenizer_vocab_mismatch: bool, checksum_mismatch_count: int,
    lineage_complete: bool, instruction_tuned: bool, evaluation_status: str | None,
    base_training_manifest_present: bool, safety_blocking_issue: bool, licence_status: str,
    model_card_status: str, manifest_mismatch: bool, resource_requirement_unknown: bool,
    rollback_target_available: bool,
) -> dict[str, Any]:
    return {
        "artifact_integrity": "fail" if checksum_mismatch_count > 0 else "pass",
        "lineage_completeness": "pass" if lineage_complete else "fail",
        "tokenizer_compatibility": (
            "fail" if (tokenizer_missing or tokenizer_vocab_mismatch) else "pass"
        ),
        "model_config_compatibility": "fail" if model_config_missing else "pass",
        "checkpoint_integrity": "fail" if (checkpoint_missing or checkpoint_corrupt) else "pass",
        "training_evidence": "pass" if base_training_manifest_present else "fail",
        "instruction_tuning_evidence": (
            "not_applicable" if not instruction_tuned
            else "pass" if instruction_tuned else "fail"
        ),
        "evaluation_evidence": evaluation_status or "not_assessed",
        "safety_evidence": "fail" if safety_blocking_issue else "pass",
        "licence_completeness": licence_status,
        "model_card_completeness": model_card_status,
        "manifest_integrity": "fail" if manifest_mismatch else "pass",
        "resource_compatibility": "unknown" if resource_requirement_unknown else "known",
        "rollback_readiness": "available" if rollback_target_available else "unavailable",
    }


def classify_resource_requirements(
    *,
    actual_parameter_count: int,
    estimated_inference_memory_bytes: int,
    estimated_training_memory_bytes: int,
    context_length: int,
) -> dict[str, Any]:
    """Bounded, deterministic classification from actually-measured values —
    never a fabricated benchmark. Latency/RAM bands are coarse, documented
    categories, not claimed measurements of real hardware throughput."""

    min_ram_bytes = int(estimated_inference_memory_bytes * 1.2)
    recommended_ram_bytes = int(estimated_training_memory_bytes * 1.2)
    if actual_parameter_count < 10_000_000:
        latency_category = "interactive_cpu_bounded"
    elif actual_parameter_count < 100_000_000:
        latency_category = "moderate_cpu_bounded"
    else:
        latency_category = "slow_cpu_bounded"
    return {
        "parameter_count": actual_parameter_count,
        "estimated_inference_memory_bytes": estimated_inference_memory_bytes,
        "estimated_training_memory_bytes": estimated_training_memory_bytes,
        "minimum_ram_bytes": min_ram_bytes,
        "recommended_ram_bytes": recommended_ram_bytes,
        "cpu_compatible": True,
        "gpu_required": False,
        "maximum_context_length": context_length,
        "expected_latency_category": latency_category,
        "supported_dtype": "float32",
        "batch_size_guidance": "batch_size=1-2 recommended on CPU at this scale",
    }
