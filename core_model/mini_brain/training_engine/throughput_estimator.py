"""MB-22: Throughput Estimator -- pure. Computes real, measured
throughput from two already-recorded metric points -- never a
fabricated or assumed rate.
"""

from __future__ import annotations

from typing import Any


def estimate_throughput(
    *, previous_step: int, previous_recorded_at_epoch_seconds: float, current_step: int,
    current_recorded_at_epoch_seconds: float, examples_per_step: int,
) -> dict[str, Any]:
    elapsed_seconds = current_recorded_at_epoch_seconds - previous_recorded_at_epoch_seconds
    step_delta = current_step - previous_step
    if elapsed_seconds <= 0 or step_delta <= 0:
        return {
            "examples_per_second": None, "steps_per_second": None, "elapsed_seconds": elapsed_seconds,
            "disclosure": "insufficient elapsed time or step progress to compute a real rate -- never fabricated",
        }
    steps_per_second = step_delta / elapsed_seconds
    examples_per_second = steps_per_second * examples_per_step
    return {
        "examples_per_second": round(examples_per_second, 3), "steps_per_second": round(steps_per_second, 4),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "disclosure": "computed from two real, already-recorded metric timestamps -- never an assumed or theoretical rate",
    }
