"""Deterministic training-process quality scoring.

This module scores the *integrity of the training process* only. It never
scores or claims anything about language fluency, chat quality, hallucination
safety, or instruction-following ability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core_model.training.diagnostics import loss_improvement_ratio, train_validation_gap

DIMENSIONS = (
    "data_integrity",
    "stream_integrity",
    "training_stability",
    "loss_improvement",
    "validation_behavior",
    "checkpoint_integrity",
    "resume_integrity",
    "worker_integrity",
    "resource_compliance",
    "coverage_quality",
)

READY_FOR_STAGING = "ready_for_staging"
WARNING = "warning"
BLOCKED = "blocked"
NOT_ASSESSED = "not_assessed"

_BLOCKING_SEVERITY_STATUS = {"blocking": BLOCKED}


@dataclass(frozen=True)
class QualityThresholds:
    min_processed_tokens: int
    min_loss_improvement_ratio: float
    max_train_validation_gap: float
    max_excluded_record_ratio: float
    min_validation_tokens: int
    require_validation: bool
    require_resume_check_if_resumed: bool
    max_non_finite_events: int
    require_all_checkpoints_verified: bool
    min_coverage_ratio: float


@dataclass
class QualityIssue:
    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _issue(code: str, severity: str, message: str, **details: Any) -> QualityIssue:
    return QualityIssue(code=code, severity=severity, message=message, details=details)


def assess(inputs: dict[str, Any], thresholds: QualityThresholds) -> dict[str, Any]:
    scores: dict[str, float] = {}
    issues: list[QualityIssue] = []

    integrity_ok = (
        inputs.get("dataset_checksum_valid", False)
        and inputs.get("tokenizer_checksum_valid", False)
        and inputs.get("model_config_checksum_valid", False)
    )
    scores["data_integrity"] = 1.0 if integrity_ok else 0.0
    if not inputs.get("dataset_checksum_valid", False):
        issues.append(
            _issue(
                "dataset_checksum_mismatch",
                "blocking",
                "dataset checksum does not match the recorded manifest",
            )
        )
    if not inputs.get("tokenizer_checksum_valid", False):
        issues.append(
            _issue(
                "tokenizer_checksum_mismatch",
                "blocking",
                "tokenizer checksum does not match the recorded manifest",
            )
        )
    if not inputs.get("model_config_checksum_valid", False):
        issues.append(
            _issue(
                "model_config_mismatch",
                "blocking",
                "model config checksum does not match the recorded manifest",
            )
        )

    stream_ok = inputs.get("stream_checksum_valid", False)
    scores["stream_integrity"] = 1.0 if stream_ok else 0.0
    if not stream_ok:
        issues.append(
            _issue(
                "stream_checksum_mismatch",
                "blocking",
                "regenerated stream checksum does not match the stored manifest",
            )
        )

    non_finite = int(inputs.get("non_finite_event_count", 0))
    diverging = bool(inputs.get("loss_diverging", False))
    stability_score = 1.0
    if non_finite > thresholds.max_non_finite_events:
        stability_score = 0.0
        issues.append(
            _issue(
                "non_finite_loss",
                "blocking",
                "training produced non-finite loss or gradient values",
                count=non_finite,
            )
        )
    if diverging:
        stability_score = min(stability_score, 0.3)
        issues.append(
            _issue("loss_divergence", "error", "training loss is diverging rather than improving")
        )
    scores["training_stability"] = stability_score

    ratio = loss_improvement_ratio(
        inputs.get("initial_training_loss"), inputs.get("final_training_loss")
    )
    if ratio is None:
        scores["loss_improvement"] = 0.0
        issues.append(
            _issue(
                "loss_not_improving",
                "warning",
                "training loss improvement could not be computed",
            )
        )
    else:
        scores["loss_improvement"] = max(0.0, min(1.0, ratio))
        if ratio < thresholds.min_loss_improvement_ratio:
            issues.append(
                _issue(
                    "loss_not_improving",
                    "warning",
                    "training loss did not improve by the configured minimum ratio",
                    ratio=ratio,
                    required_ratio=thresholds.min_loss_improvement_ratio,
                )
            )

    validation_loss = inputs.get("final_validation_loss")
    validation_tokens = int(inputs.get("validation_tokens", 0))
    validation_score = 1.0
    if validation_loss is None:
        if thresholds.require_validation:
            validation_score = 0.0
            issues.append(
                _issue("validation_loss_missing", "blocking", "required validation loss is missing")
            )
        else:
            validation_score = 0.5
    else:
        best_validation_loss = inputs.get("best_validation_loss")
        if best_validation_loss is not None and validation_loss > best_validation_loss:
            validation_score = 0.6
            issues.append(
                _issue(
                    "validation_loss_worsening",
                    "warning",
                    "final validation loss is worse than the best observed validation loss",
                    final=validation_loss,
                    best=best_validation_loss,
                )
            )
        gap = train_validation_gap(inputs.get("final_training_loss"), validation_loss)
        if gap is not None and gap > thresholds.max_train_validation_gap:
            validation_score = min(validation_score, 0.5)
            issues.append(
                _issue(
                    "train_validation_gap_high",
                    "warning",
                    "gap between training and validation loss exceeds the configured maximum",
                    gap=gap,
                )
            )
    if validation_tokens < thresholds.min_validation_tokens:
        validation_score = min(validation_score, 0.5)
        issues.append(
            _issue(
                "too_few_validation_tokens",
                "warning",
                "validation split produced fewer tokens than the configured minimum",
                tokens=validation_tokens,
                required=thresholds.min_validation_tokens,
            )
        )
    scores["validation_behavior"] = validation_score

    all_verified = inputs.get("all_checkpoints_verified", False)
    scores["checkpoint_integrity"] = 1.0 if all_verified else 0.0
    if thresholds.require_all_checkpoints_verified and not all_verified:
        issues.append(
            _issue("checkpoint_corrupt", "blocking", "one or more checkpoints failed verification")
        )

    was_resumed = bool(inputs.get("was_resumed", False))
    resume_consistent = inputs.get("resume_consistent")
    if not was_resumed:
        scores["resume_integrity"] = 1.0
    elif resume_consistent:
        scores["resume_integrity"] = 1.0
    else:
        scores["resume_integrity"] = 0.0
        if thresholds.require_resume_check_if_resumed:
            issues.append(
                _issue(
                    "resume_inconsistent",
                    "blocking",
                    "resumed job failed optimizer-step resume verification",
                )
            )

    lease_conflicts = int(inputs.get("lease_conflict_count", 0))
    stale_writes = int(inputs.get("stale_write_rejections", 0))
    recovery_failures = int(inputs.get("worker_recovery_failures", 0))
    worker_score = 1.0
    if lease_conflicts:
        worker_score = min(worker_score, 0.7)
        issues.append(
            _issue(
                "worker_lease_conflict",
                "warning",
                "worker lease conflicts were detected during training",
                count=lease_conflicts,
            )
        )
    if stale_writes:
        worker_score = min(worker_score, 0.5)
        issues.append(
            _issue(
                "stale_worker_write",
                "error",
                "a stale worker attempted to write after lease takeover",
                count=stale_writes,
            )
        )
    if recovery_failures:
        worker_score = min(worker_score, 0.5)
        issues.append(
            _issue(
                "worker_recovery_failed",
                "error",
                "one or more recovery attempts failed",
                count=recovery_failures,
            )
        )
    scores["worker_integrity"] = worker_score

    resource_score = 1.0
    if inputs.get("memory_limit_exceeded", False):
        resource_score = 0.0
        issues.append(
            _issue(
                "memory_limit_exceeded",
                "error",
                "training exceeded the configured memory limit",
            )
        )
    if inputs.get("disk_limit_exceeded", False):
        resource_score = 0.0
        issues.append(
            _issue(
                "disk_limit_exceeded",
                "error",
                "checkpoint storage exceeded the configured disk limit",
            )
        )
    if inputs.get("throughput_unusually_low", False):
        resource_score = min(resource_score, 0.7)
        issues.append(
            _issue(
                "throughput_unusually_low",
                "info",
                "observed throughput is unusually low for this configuration",
            )
        )
    scores["resource_compliance"] = resource_score

    coverage_ratio = float(inputs.get("coverage_ratio", 0.0))
    excluded_ratio = float(inputs.get("excluded_record_ratio", 0.0))
    processed_tokens = int(inputs.get("processed_tokens", 0))
    coverage_score = 1.0
    if coverage_ratio < thresholds.min_coverage_ratio:
        coverage_score = min(coverage_score, coverage_ratio)
        issues.append(
            _issue(
                "coverage_too_low",
                "warning",
                "dataset coverage ratio is below the configured minimum",
                ratio=coverage_ratio,
                required=thresholds.min_coverage_ratio,
            )
        )
    if excluded_ratio > thresholds.max_excluded_record_ratio:
        coverage_score = min(coverage_score, 1 - excluded_ratio)
        issues.append(
            _issue(
                "too_many_excluded_records",
                "warning",
                "excluded record ratio exceeds the configured maximum",
                ratio=excluded_ratio,
                allowed=thresholds.max_excluded_record_ratio,
            )
        )
    if processed_tokens < thresholds.min_processed_tokens:
        coverage_score = min(coverage_score, 0.3)
        issues.append(
            _issue(
                "insufficient_training_tokens",
                "warning",
                "processed token count is below the configured minimum",
                tokens=processed_tokens,
                required=thresholds.min_processed_tokens,
            )
        )
    scores["coverage_quality"] = max(0.0, min(1.0, coverage_score))

    overall_score = sum(scores[dimension] for dimension in DIMENSIONS) / len(DIMENSIONS)

    if any(issue.severity == "blocking" for issue in issues):
        readiness = BLOCKED
    elif issues:
        readiness = WARNING
    else:
        readiness = READY_FOR_STAGING

    return {
        "dimension_scores": scores,
        "overall_score": overall_score,
        "readiness_status": readiness,
        "issues": [
            {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "details": issue.details,
            }
            for issue in issues
        ],
    }
