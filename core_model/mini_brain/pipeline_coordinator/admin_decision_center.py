"""MB-12: Admin Decision Center -- pure. Validates one of the task's
own nine named admin decisions against the pipeline's current stage
and evidence, returning the status it maps to and any advisory
warnings. No decision here executes anything -- this module only
decides what to record and whether to warn the admin the decision
looks premature or redundant given the current stage.
"""

from __future__ import annotations

from typing import Any

DECISIONS = (
    "continue", "pause", "research_more", "request_providers", "improve_dataset", "retry_rag",
    "approve_training", "reject", "archive",
)
STATUS_MAP: dict[str, str] = {
    "continue": "in_progress", "pause": "admin_paused", "research_more": "admin_requested_more_research",
    "request_providers": "admin_requested_providers",
    "improve_dataset": "admin_requested_dataset_improvement", "retry_rag": "admin_retried_rag",
    "approve_training": "admin_approved_training", "reject": "admin_rejected", "archive": "admin_archived",
}
_TRAINING_READY_STAGES = {"rag_testing", "training_candidate"}


def evaluate_decision(*, decision: str, current_stage: str, rag_gate_passed: bool | None) -> dict[str, Any]:
    warnings: list[str] = []

    if decision == "approve_training" and current_stage not in _TRAINING_READY_STAGES:
        warnings.append(
            f"approve_training recorded while the pipeline is at '{current_stage}', not yet at "
            "'rag_testing' or 'training_candidate' -- this only records the admin's intent, it does "
            "not start training and does not skip the RAG gate"
        )
    if decision == "retry_rag" and rag_gate_passed is True:
        warnings.append("retry_rag recorded even though the RAG gate already passed -- treated as an explicit admin override")
    if decision == "archive" and current_stage in {"completed"}:
        warnings.append("archiving an already-completed pipeline -- historical record only")

    return {
        "decision": decision, "status": STATUS_MAP[decision],
        "stage_override": "archived" if decision == "archive" else None,
        "warnings": warnings, "executes_nothing": True,
    }
