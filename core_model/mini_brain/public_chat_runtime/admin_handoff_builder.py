"""MB-23: Admin Handoff Builder -- pure. Assembles the structured,
advisory-only handoff package the task spec's own Step 10 names --
candidate summary, example anonymized questions, suggested missing
knowledge, and a recommended next phase. This module never creates,
starts, or approves anything in MB-13/16/18/21/22; it only formats
already-computed candidate data for a human admin to act on (or not)
through those phases' own existing admin-governed workflows.
"""

from __future__ import annotations

from typing import Any

_NEXT_PHASE_LABELS = {
    "mb13_cleanup": "MB-13 cleanup",
    "mb16_dataset_draft": "MB-16 dataset draft",
    "mb21_external_evaluation": "MB-21 external evaluation",
    "mb18_package_refresh": "MB-18 package refresh",
    "mb22_retraining_request": "MB-22 retraining request",
}


def build_admin_handoff(
    *, topic: str, topic_key: str, frequency: int, priority_score: float, recommended_action: str,
    example_questions: list[str], suggested_missing_knowledge: dict[str, Any],
) -> dict[str, Any]:
    next_phase_label = _NEXT_PHASE_LABELS.get(recommended_action, _NEXT_PHASE_LABELS["mb13_cleanup"])
    return {
        "candidate_summary": (
            f"{frequency} occurrence(s) observed for topic '{topic}' (priority score {priority_score})."
        ),
        "example_anonymized_questions": example_questions[:5],
        "suggested_missing_knowledge": suggested_missing_knowledge,
        "recommended_next_phase": next_phase_label,
        "recommended_action_key": recommended_action,
        "advisory_only": True,
        "disclosure": (
            "this handoff is advisory only -- it never creates, starts, or approves anything in "
            "MB-13/16/18/21/22; a human admin must take every next action explicitly through those "
            "phases' own existing admin-governed workflows"
        ),
    }
