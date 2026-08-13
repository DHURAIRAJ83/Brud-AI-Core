"""MB-20: Operator Instruction Builder -- pure. A fixed, ordered list
of manual steps a human operator would follow to deploy this release
candidate -- documentation only. This module never executes any of
these steps and never calls a runtime, deployment, or infrastructure
API itself.
"""

from __future__ import annotations

from typing import Any

INSTRUCTION_STEPS = (
    "Confirm this release session's own status is admin_approved before proceeding.",
    "Verify every release artifact's SHA-256 checksum against release_manifest.json.",
    "Confirm every deployment prerequisite in deployment_prerequisites.json is verified.",
    "Stage the release candidate's model artifact on the target host, without activating it.",
    "Follow the target runtime's own startup procedure to activate the release (outside this codebase).",
    "Run the target environment's own smoke checks against the newly activated release.",
    "Monitor the rollback_plan.json trigger conditions for the agreed observation window.",
    "Record the deployment outcome back into this release session's own audit trail.",
)


def build_operator_instructions(*, release_topic: str, release_readiness_status: str) -> dict[str, Any]:
    return {
        "release_topic": release_topic, "release_readiness_status": release_readiness_status,
        "steps": [{"order": i, "instruction": step} for i, step in enumerate(INSTRUCTION_STEPS, start=1)],
        "step_count": len(INSTRUCTION_STEPS),
        "executed_by_this_phase": False,
        "disclosure": (
            "a fixed, ordered manual procedure for a human operator -- this module never executes any "
            "step and never calls a runtime, deployment, or infrastructure API; actual deployment "
            "always happens outside this codebase"
        ),
    }
