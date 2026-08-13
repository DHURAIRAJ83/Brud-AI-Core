"""MB-06: Training Result Analyzer -- pure. Reuses
`core_model.training.diagnostics` (`loss_improvement_ratio`,
`train_validation_gap`, `is_diverging`, `safe_perplexity`) UNCHANGED
for the actual overfitting/underfitting/divergence math -- this module
only adds threshold classification and checkpoint-integrity
summarization on top of those already-real, already-tested formulas.
"""

from __future__ import annotations

from typing import Any

from core_model.training.diagnostics import (
    is_diverging,
    loss_improvement_ratio,
    safe_perplexity,
    train_validation_gap,
)

OVERFITTING_GAP_THRESHOLD = 0.5
UNDERFITTING_IMPROVEMENT_THRESHOLD = 0.1


def analyze_training_result(
    *,
    job: dict[str, Any],
    step_losses: list[float],
    checkpoints: list[dict[str, Any]],
) -> dict[str, Any]:
    initial_loss = job.get("initial_training_loss")
    final_loss = job.get("latest_training_loss")
    validation_loss = job.get("latest_validation_loss")

    gap = train_validation_gap(final_loss, validation_loss)
    improvement_ratio = loss_improvement_ratio(initial_loss, final_loss)
    diverging = is_diverging(step_losses) if step_losses else False
    perplexity = safe_perplexity(validation_loss)

    indicators: list[str] = []
    if gap is not None and gap > OVERFITTING_GAP_THRESHOLD:
        indicators.append(f"overfitting_signal: validation loss exceeds training loss by {round(gap, 3)}")
    if improvement_ratio is not None and improvement_ratio < UNDERFITTING_IMPROVEMENT_THRESHOLD:
        indicators.append(f"underfitting_signal: loss only improved by {round(improvement_ratio * 100, 1)}% from initial")
    if diverging:
        indicators.append("divergence_signal: training loss trended upward across the run")

    status = job.get("status")
    failed = status == "failed"
    interrupted = status in ("paused", "cancelled")

    verified_checkpoints = sum(1 for c in checkpoints if c.get("status") == "verified")
    corrupt_checkpoints = sum(1 for c in checkpoints if c.get("status") == "corrupt")

    return {
        "job_status": status,
        "failed": failed,
        "interrupted": interrupted,
        "initial_training_loss": initial_loss,
        "final_training_loss": final_loss,
        "validation_loss": validation_loss,
        "validation_perplexity": perplexity,
        "train_validation_gap": gap,
        "loss_improvement_ratio": improvement_ratio,
        "diverging": diverging,
        "indicators": indicators,
        "checkpoint_summary": {
            "total": len(checkpoints), "verified": verified_checkpoints, "corrupt": corrupt_checkpoints,
        },
    }
