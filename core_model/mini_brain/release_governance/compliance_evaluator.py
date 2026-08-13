"""MB-20: Compliance Evaluator -- pure. A checklist only -- this module
makes no legal judgment and offers no legal advice; it verifies that
specific pieces of governance evidence exist, nothing more.

Some checklist items (rollback plan, operator instructions, deployment
prerequisites) are only built in a later workflow stage than the
compliance gate itself runs in (Step 7 runs before Step 9's risk/
rollback build and Step 10's package build). Rather than force those
items to a fabricated "present" or a misleading hard "fail" before the
workflow has even reached that stage, an item not yet built is
reported as `"pending"` -- informational, not blocking -- unless the
caller explicitly marks it `required_now` (used for the items that
genuinely must already exist by the time this runs: dataset approval
and the audit trail). The service re-runs this same function with a
complete `required_now` set once every artifact has actually been
built, to produce the final compliance verdict in the readiness report.
"""

from __future__ import annotations

from typing import Any

COMPLIANCE_ITEMS = (
    "dataset_approval_present", "audit_trail_present", "reproducibility_hash_present",
    "artifact_checksums_present", "rollback_plan_present", "operator_instructions_present",
    "deployment_prerequisites_present",
)


def run_compliance_gates(*, checklist: dict[str, bool], required_now: set[str]) -> dict[str, Any]:
    items = []
    blocking_reasons: list[str] = []
    for name in COMPLIANCE_ITEMS:
        present = bool(checklist.get(name, False))
        if present:
            status = "present"
        elif name in required_now:
            status = "missing"
            blocking_reasons.append(f"{name} is required at this stage but not yet present")
        else:
            status = "pending"
        items.append({"name": name, "status": status})

    if blocking_reasons:
        overall_status = "fail"
    elif all(item["status"] == "present" for item in items):
        overall_status = "complete"
    else:
        overall_status = "in_progress"

    return {
        "items": items,
        "overall_status": overall_status,
        "blocking_reasons": blocking_reasons,
        "disclosure": (
            "a checklist only, never a legal certification or legal advice -- each item verifies that "
            "a specific piece of governance evidence exists, not that it satisfies any external "
            "regulatory requirement"
        ),
    }
