"""MB-12: Dependency Coordinator -- pure. Enforces "never allow stage
skipping": a requested stage transition is only legal if it is exactly
one step forward in `state_machine.STAGE_ORDER`, one of the small set
of allowed alternate paths (`state_machine.ALLOWED_ALTERNATE_TRANSITIONS`),
or the always-allowed admin override to `archived` -- and the specific
evidence that stage requires is already present. Never advances
anything itself -- the service applies this check before writing a new
stage.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.pipeline_coordinator.state_machine import (
    is_allowed_alternate_transition,
    is_one_step_forward,
)

REQUIRED_EVIDENCE_BY_STAGE: dict[str, tuple[str, ...]] = {
    "under_research": ("mb09_linked",),
    "provider_consensus_pending": ("mb10_linked",),
    "draft_ready": ("mb10_linked",),
    "dataset_planned": ("mb11_linked",),
    "rag_testing": ("rag_passed",),
    "training_candidate": ("mb06_linked",),
    "training_running": ("mb06_job_running",),
    "benchmark_ready": ("mb06_benchmark_ready",),
    "release_candidate": ("mb06_release_candidate_present",),
    "completed": ("mb06_accepted",),
}


def check_dependencies(*, current_stage: str, target_stage: str, evidence: dict[str, Any]) -> dict[str, Any]:
    if target_stage == current_stage:
        return {"allowed": False, "reasons": ["already at this stage"], "target_stage": target_stage}

    reasons: list[str] = []
    is_alternate = is_allowed_alternate_transition(current_stage=current_stage, target_stage=target_stage)
    is_forward = target_stage != "archived" and is_one_step_forward(current_stage=current_stage, target_stage=target_stage)

    if target_stage != "archived" and not (is_forward or is_alternate):
        reasons.append(f"cannot move from '{current_stage}' directly to '{target_stage}' -- stages cannot be skipped")

    for key in REQUIRED_EVIDENCE_BY_STAGE.get(target_stage, ()):
        if not evidence.get(key):
            reasons.append(f"missing required evidence: {key}")

    return {"allowed": not reasons, "reasons": reasons, "target_stage": target_stage}
