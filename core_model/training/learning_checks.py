"""Deterministic Phase 11 learning checks, generalization, and memorization
classification.

These functions score whether a base-pretraining run shows genuine evidence
of learning versus optimization alone. They never claim proven language
understanding — only bounded, honest evidence categories.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

CHECK_CODES = (
    "training_loss_improves",
    "validation_loss_finite",
    "test_loss_finite",
    "no_non_finite_gradients",
    "checkpoint_integrity",
    "dataset_stream_integrity",
    "language_metrics_complete",
    "generalization_gap_bounded",
    "memorization_risk_bounded",
    "tokenizer_coverage_adequate",
    "resource_limits_respected",
)

PASS = "pass"
WARNING = "warning"
FAIL = "fail"

OPTIMIZATION_SUCCESS_ONLY = "optimization_success_only"
LIMITED_GENERALIZATION_EVIDENCE = "limited_generalization_evidence"
NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True)
class LearningCheckThresholds:
    generalization_max_gap: float
    memorization_max_gap: float
    tokenizer_max_unknown_rate: float


def _check(code: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    return {"check_code": code, "status": status, "message": message, "details": details}


def run_learning_checks(
    inputs: dict[str, Any], thresholds: LearningCheckThresholds
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    initial = inputs.get("initial_training_loss")
    final = inputs.get("final_training_loss")
    if initial is None or final is None:
        checks.append(_check("training_loss_improves", FAIL, "training loss values missing"))
    elif final < initial:
        checks.append(
            _check(
                "training_loss_improves", PASS, "training loss decreased",
                initial=initial, final=final,
            )
        )
    else:
        checks.append(
            _check(
                "training_loss_improves", FAIL, "training loss did not decrease",
                initial=initial, final=final,
            )
        )

    validation_loss = inputs.get("validation_loss")
    if validation_loss is None:
        checks.append(_check("validation_loss_finite", FAIL, "validation loss missing"))
    elif math.isfinite(validation_loss):
        checks.append(
            _check(
                "validation_loss_finite", PASS, "validation loss is finite", value=validation_loss
            )
        )
    else:
        checks.append(_check("validation_loss_finite", FAIL, "validation loss is not finite"))

    test_loss = inputs.get("test_loss")
    if test_loss is None:
        checks.append(
            _check(
                "test_loss_finite", WARNING,
                "test loss not evaluated (not yet run, or TEST_EVALUATION_NOT_RELIABLE)",
            )
        )
    elif math.isfinite(test_loss):
        checks.append(_check("test_loss_finite", PASS, "test loss is finite", value=test_loss))
    else:
        checks.append(_check("test_loss_finite", FAIL, "test loss is not finite"))

    non_finite_events = inputs.get("non_finite_event_count", 0)
    if non_finite_events == 0:
        checks.append(
            _check("no_non_finite_gradients", PASS, "no non-finite gradient/loss events recorded")
        )
    else:
        checks.append(
            _check(
                "no_non_finite_gradients", FAIL,
                f"{non_finite_events} non-finite events recorded",
                count=non_finite_events,
            )
        )

    if inputs.get("checkpoint_verified", False):
        checks.append(_check("checkpoint_integrity", PASS, "checkpoint verified"))
    else:
        checks.append(_check("checkpoint_integrity", FAIL, "checkpoint not verified"))

    if inputs.get("stream_verified", False):
        checks.append(_check("dataset_stream_integrity", PASS, "stream checksum verified"))
    else:
        checks.append(
            _check("dataset_stream_integrity", FAIL, "stream checksum could not be verified")
        )

    languages_present = set(inputs.get("languages_with_metrics", ()))
    languages_expected = set(inputs.get("languages_expected", ()))
    missing = languages_expected - languages_present
    if not missing:
        checks.append(
            _check(
                "language_metrics_complete", PASS,
                "language metrics present for all available languages",
            )
        )
    else:
        checks.append(
            _check(
                "language_metrics_complete", WARNING,
                f"missing language metrics for: {sorted(missing)}", missing=sorted(missing),
            )
        )

    gap = inputs.get("train_validation_gap")
    if gap is None:
        checks.append(_check("generalization_gap_bounded", WARNING, "gap could not be computed"))
    elif gap <= thresholds.generalization_max_gap:
        checks.append(
            _check(
                "generalization_gap_bounded", PASS,
                "train/validation gap is within bounds", gap=gap,
            )
        )
    else:
        checks.append(
            _check(
                "generalization_gap_bounded", WARNING,
                "train/validation gap exceeds the configured bound", gap=gap,
            )
        )

    very_low_train_loss = final is not None and final < 0.05
    if gap is not None and gap > thresholds.memorization_max_gap and very_low_train_loss:
        checks.append(
            _check(
                "memorization_risk_bounded", WARNING,
                "unusually low training loss with a large validation gap suggests memorization",
                gap=gap,
            )
        )
    else:
        checks.append(
            _check("memorization_risk_bounded", PASS, "no strong memorization signal detected")
        )

    unknown_rate = inputs.get("unknown_token_rate", 0.0)
    if unknown_rate <= thresholds.tokenizer_max_unknown_rate:
        checks.append(
            _check(
                "tokenizer_coverage_adequate", PASS, "unknown-token rate is acceptable",
                unknown_rate=unknown_rate,
            )
        )
    else:
        checks.append(
            _check(
                "tokenizer_coverage_adequate", WARNING, "unknown-token rate is high",
                unknown_rate=unknown_rate,
            )
        )

    if inputs.get("resource_limit_exceeded", False):
        checks.append(
            _check(
                "resource_limits_respected", FAIL,
                "resource limits were exceeded during the run",
            )
        )
    else:
        checks.append(
            _check(
                "resource_limits_respected", PASS,
                "resource usage stayed within configured limits",
            )
        )

    return checks


def classify_generalization(
    *,
    train_initial: float | None,
    train_final: float | None,
    validation_initial: float | None,
    validation_final: float | None,
    languages_with_improvement: int,
) -> str:
    if validation_final is None:
        return NOT_ASSESSED
    training_improved = (
        train_final is not None and train_initial is not None and train_final < train_initial
    )
    if not training_improved:
        return NOT_ASSESSED
    validation_improved = (
        validation_initial is not None and validation_final < validation_initial
    )
    if validation_improved and languages_with_improvement >= 1:
        return LIMITED_GENERALIZATION_EVIDENCE
    return OPTIMIZATION_SUCCESS_ONLY


def memorization_warnings(
    *,
    train_loss: float | None,
    validation_loss: float | None,
    duplicate_rate: float,
    near_duplicate_rate: float,
    thresholds: LearningCheckThresholds,
    duplicate_max_ratio: float,
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if train_loss is not None and validation_loss is not None:
        gap = validation_loss - train_loss
        if train_loss < 0.05 and gap > thresholds.memorization_max_gap:
            warnings.append(
                {
                    "code": "low_train_high_validation_gap",
                    "message": "training loss is unusually low relative to validation loss",
                    "gap": gap,
                }
            )
    if duplicate_rate > duplicate_max_ratio:
        warnings.append(
            {
                "code": "high_duplicate_rate",
                "message": "dataset duplicate rate is high enough to risk leakage",
                "duplicate_rate": duplicate_rate,
            }
        )
    if near_duplicate_rate > duplicate_max_ratio:
        warnings.append(
            {
                "code": "high_near_duplicate_rate",
                "message": "dataset near-duplicate rate is high enough to risk leakage",
                "near_duplicate_rate": near_duplicate_rate,
            }
        )
    return warnings
