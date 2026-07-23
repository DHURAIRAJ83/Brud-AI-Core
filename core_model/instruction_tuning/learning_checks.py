"""The 12 required Phase 12 instruction-tuning learning-evidence checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

CHECK_CODES = (
    "response_only_masking_verified",
    "training_loss_improves",
    "validation_response_loss_finite",
    "language_metrics_complete",
    "instruction_format_compliance",
    "role_token_leakage_bounded",
    "prompt_leakage_bounded",
    "repetition_bounded",
    "memorization_risk_bounded",
    "checkpoint_integrity",
    "base_model_lineage_complete",
    "resource_limits_respected",
)

PASS = "pass"
WARNING = "warning"
FAIL = "fail"


@dataclass(frozen=True)
class InstructionLearningCheckThresholds:
    max_role_leakage_rate: float = 0.0
    max_prompt_leakage_rate: float = 0.1
    max_repetition_rate: float = 0.2


def _check(code: str, status: str, message: str, **details: Any) -> dict[str, Any]:
    return {"check_code": code, "status": status, "message": message, "details": details}


def run_learning_checks(
    inputs: dict[str, Any], thresholds: InstructionLearningCheckThresholds
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    target_tokens = inputs.get("assistant_target_tokens", 0)
    prompt_tokens = inputs.get("prompt_tokens", 0)
    if target_tokens > 0 and prompt_tokens > 0:
        checks.append(
            _check(
                "response_only_masking_verified", PASS,
                "assistant-response targets and masked prompt tokens both present",
                target_tokens=target_tokens, prompt_tokens=prompt_tokens,
            )
        )
    else:
        checks.append(
            _check(
                "response_only_masking_verified", FAIL,
                "no masked prompt tokens or no trainable assistant targets recorded",
                target_tokens=target_tokens, prompt_tokens=prompt_tokens,
            )
        )

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

    validation_loss = inputs.get("validation_response_loss")
    if validation_loss is not None and math.isfinite(validation_loss):
        checks.append(
            _check(
                "validation_response_loss_finite", PASS, "validation response loss is finite",
                value=validation_loss,
            )
        )
    else:
        checks.append(
            _check(
                "validation_response_loss_finite", FAIL,
                "validation response loss missing or non-finite",
            )
        )

    missing_languages = set(inputs.get("languages_expected", ())) - set(
        inputs.get("languages_with_metrics", ())
    )
    if not missing_languages:
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
                f"missing language metrics for: {sorted(missing_languages)}",
                missing=sorted(missing_languages),
            )
        )

    format_status = inputs.get("instruction_format_status", FAIL)
    checks.append(
        _check(
            "instruction_format_compliance", format_status,
            f"instruction format compliance: {format_status}",
        )
    )

    role_leakage_rate = inputs.get("role_leakage_rate", 0.0)
    if role_leakage_rate <= thresholds.max_role_leakage_rate:
        checks.append(
            _check(
                "role_token_leakage_bounded", PASS, "no role-token leakage detected",
                rate=role_leakage_rate,
            )
        )
    else:
        checks.append(
            _check(
                "role_token_leakage_bounded", FAIL,
                "role tokens leaked into generated responses", rate=role_leakage_rate,
            )
        )

    prompt_leakage_rate = inputs.get("prompt_leakage_rate", 0.0)
    if prompt_leakage_rate <= thresholds.max_prompt_leakage_rate:
        checks.append(
            _check(
                "prompt_leakage_bounded", PASS, "prompt leakage within bounds",
                rate=prompt_leakage_rate,
            )
        )
    else:
        checks.append(
            _check(
                "prompt_leakage_bounded", WARNING if prompt_leakage_rate < 0.5 else FAIL,
                "prompt leakage rate exceeds the configured bound", rate=prompt_leakage_rate,
            )
        )

    repetition_rate = inputs.get("repetition_rate", 0.0)
    if repetition_rate <= thresholds.max_repetition_rate:
        checks.append(
            _check(
                "repetition_bounded", PASS, "repetition within bounds", rate=repetition_rate,
            )
        )
    else:
        checks.append(
            _check(
                "repetition_bounded", WARNING,
                "repetition rate exceeds the configured bound", rate=repetition_rate,
            )
        )

    memorization_warning_count = inputs.get("memorization_warning_count", 0)
    if memorization_warning_count == 0:
        checks.append(
            _check("memorization_risk_bounded", PASS, "no memorization warnings detected")
        )
    else:
        checks.append(
            _check(
                "memorization_risk_bounded", WARNING,
                f"{memorization_warning_count} memorization warning(s) detected",
                count=memorization_warning_count,
            )
        )

    if inputs.get("checkpoint_verified", False):
        checks.append(_check("checkpoint_integrity", PASS, "checkpoint verified"))
    else:
        checks.append(_check("checkpoint_integrity", FAIL, "checkpoint not verified"))

    if inputs.get("base_model_lineage_complete", False):
        checks.append(
            _check(
                "base_model_lineage_complete", PASS,
                "base model/tokenizer/dataset/config lineage complete",
            )
        )
    else:
        checks.append(
            _check("base_model_lineage_complete", FAIL, "base model lineage is incomplete")
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
