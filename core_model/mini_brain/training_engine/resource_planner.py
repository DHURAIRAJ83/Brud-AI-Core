"""MB-22: Resource Planner -- pure. Re-surfaces MB-18's own already-
computed hardware estimate into a training-specific resource plan,
never re-deriving token/image counts itself. Every figure is
explicitly marked heuristic, mirroring the same disclosed-estimate
discipline `core_model.pretraining_readiness.resource_profiles` and
MB-18's own `hardware_estimator.py` already established.
"""

from __future__ import annotations

from typing import Any

DEFAULT_CPU_THREADS = 4
SIMULATION_CPU_THREADS = 1
DURATION_CATEGORIES = ("minutes", "hours", "many_hours_to_days")


def plan_resources(
    *, execution_mode: str, estimated_token_count: int, ram_tier: str, vram_tier: str,
    cpu_only_feasible: bool, estimated_disk_bytes: int, expected_training_duration_category: str,
) -> dict[str, Any]:
    if execution_mode == "simulation":
        return {
            "execution_mode": execution_mode, "required_ram_tier": "512MB+", "recommended_vram_tier": "none",
            "required_disk_bytes": 1_000_000, "cpu_thread_count": SIMULATION_CPU_THREADS,
            "expected_duration_category": "minutes", "gpu_required": False,
            "disclosure": "simulation mode performs no real computation -- these figures describe the trivial resource footprint of generating deterministic fake metrics, not real training",
        }

    gpu_required = execution_mode == "gpu"
    cpu_thread_count = DEFAULT_CPU_THREADS if cpu_only_feasible or not gpu_required else DEFAULT_CPU_THREADS * 2

    return {
        "execution_mode": execution_mode, "required_ram_tier": ram_tier,
        "recommended_vram_tier": vram_tier if gpu_required else "none",
        "required_disk_bytes": estimated_disk_bytes, "cpu_thread_count": cpu_thread_count,
        "expected_duration_category": (
            expected_training_duration_category if expected_training_duration_category in DURATION_CATEGORIES
            else "hours"
        ),
        "gpu_required": gpu_required,
        "estimated_token_count": estimated_token_count,
        "disclosure": (
            "every figure here is read from MB-18's own already-computed hardware estimate or a "
            "fixed heuristic default -- never a real hardware benchmark, never calibrated against an "
            "actual training run in this codebase"
        ),
    }
