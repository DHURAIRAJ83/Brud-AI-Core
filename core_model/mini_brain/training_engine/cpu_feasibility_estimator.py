"""MB-22: CPU Feasibility Estimator -- pure. Judges whether a CPU-only
run is feasible for this job's own already-computed resource plan --
a disclosed heuristic threshold, never a real hardware benchmark.
"""

from __future__ import annotations

from typing import Any

LARGE_TOKEN_COUNT_THRESHOLD = 5_000_000


def estimate_cpu_feasibility(*, resource_plan: dict[str, Any]) -> dict[str, Any]:
    if resource_plan.get("execution_mode") == "simulation":
        return {
            "cpu_feasible": True, "reason": "simulation mode performs no real computation",
            "disclosure": "simulation mode is always CPU-feasible since no real training occurs",
        }

    estimated_tokens = resource_plan.get("estimated_token_count", 0) or 0
    gpu_required = resource_plan.get("gpu_required", False)

    if gpu_required:
        feasible = False
        reason = "job was explicitly planned for GPU execution"
    elif estimated_tokens > LARGE_TOKEN_COUNT_THRESHOLD:
        feasible = False
        reason = f"estimated token count {estimated_tokens} exceeds the CPU-feasible threshold of {LARGE_TOKEN_COUNT_THRESHOLD}"
    else:
        feasible = True
        reason = None

    return {
        "cpu_feasible": feasible, "reason": reason, "threshold": LARGE_TOKEN_COUNT_THRESHOLD,
        "disclosure": "a fixed heuristic threshold on estimated token count -- never a real hardware benchmark",
    }
