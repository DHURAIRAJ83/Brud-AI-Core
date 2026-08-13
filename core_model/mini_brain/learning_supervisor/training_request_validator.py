"""MB-06: Training Request Validator -- pure decision function. Never
submits anything itself; only decides whether the service layer is
allowed to proceed to Stage 7 (Training Request Builder). A blocker
means Stage 7 must not run; a warning is advisory only.
"""

from __future__ import annotations

from typing import Any

NOT_READY_STATUS = "Not Ready"
NEEDS_IMPROVEMENT_STATUS = "Needs Improvement"


def validate_training_request(
    *,
    dataset_readiness: dict[str, Any],
    dataset_decision: str | None,
    rag_required: bool,
    rag_decision: str | None,
    advanced_risk: dict[str, Any] | None,
    advanced_conflicts: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    if dataset_decision != "approve":
        blockers.append("dataset readiness has not been approved by an admin")
    if rag_required and rag_decision != "approve":
        blockers.append("RAG evaluation has not been approved by an admin")

    status = dataset_readiness.get("status")
    if status == NOT_READY_STATUS:
        blockers.append(f"dataset training readiness is '{NOT_READY_STATUS}': {dataset_readiness.get('reasons')}")
    elif status == NEEDS_IMPROVEMENT_STATUS:
        warnings.append(f"dataset training readiness is '{NEEDS_IMPROVEMENT_STATUS}': {dataset_readiness.get('reasons')}")

    if advanced_risk:
        critical_items = [item for item in advanced_risk.get("risk_items", []) if item.get("severity") == "critical"]
        if critical_items:
            blockers.append(f"{len(critical_items)} critical PII/secret finding(s) must be resolved first")
        elif advanced_risk.get("risk_item_count", 0) > 0:
            warnings.append(f"{advanced_risk['risk_item_count']} non-critical PII/secret finding(s) present")

    if advanced_conflicts and advanced_conflicts.get("conflict_count", 0) > 0:
        warnings.append(f"{advanced_conflicts['conflict_count']} conflicting-answer group(s) present in the dataset")

    return {"valid": len(blockers) == 0, "blockers": blockers, "warnings": warnings}
