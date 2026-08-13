"""MB-20: Rollback Planner -- pure. Produces a structured, procedural
rollback plan as documentation only -- this module never executes a
rollback, never calls a runtime API, and never modifies any deployed
system. Trigger conditions are drawn directly from the risk register's
own already-generated rollback_trigger fields; the step lists are a
fixed, disclosed procedural template since this codebase has no live
deployment target to introspect.
"""

from __future__ import annotations

from typing import Any

ROLLBACK_STEPS = (
    "Freeze new release traffic at the point of first observing a trigger condition.",
    "Notify the release owner and on-call operator.",
    "Restore the previously active model/runtime configuration from its own last-known-good state.",
    "Confirm the restored configuration matches its own recorded checksum/manifest.",
    "Re-run the prior release's own smoke checks before resuming traffic.",
)

VERIFICATION_STEPS = (
    "Confirm the restored version is serving and matches its recorded version identifier.",
    "Confirm no partial state from the rolled-back release remains active.",
    "Confirm monitoring/alerting reflects the restored version, not the rolled-back one.",
)

COMMUNICATION_CHECKLIST = (
    "Notify the release owner that a rollback occurred and why.",
    "Record the rollback in the release's own permanent audit trail.",
    "Summarize the rollback and its trigger for the next release review.",
)


def build_rollback_plan(*, risk_register: dict[str, Any]) -> dict[str, Any]:
    trigger_conditions = [entry["rollback_trigger"] for entry in risk_register.get("entries", [])]
    if not trigger_conditions:
        trigger_conditions = ["no specific risk-derived trigger was identified -- fall back to any post-release safety gate failure"]

    return {
        "trigger_conditions": trigger_conditions,
        "rollback_steps": list(ROLLBACK_STEPS),
        "verification_steps": list(VERIFICATION_STEPS),
        "communication_checklist": list(COMMUNICATION_CHECKLIST),
        "executed": False,
        "disclosure": (
            "this is a procedural document only -- no rollback automation exists in this codebase, "
            "and this module never calls any runtime, deployment, or infrastructure API. Trigger "
            "conditions are drawn directly from the risk register's own findings; the step lists are "
            "a fixed, generic procedural template, not integration-tested automation"
        ),
    }
