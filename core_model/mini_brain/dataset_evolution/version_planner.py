"""MB-11: Dataset Version Planner -- pure. Projects a future dataset
version's size, growth, compatibility, risk, and migration notes from
the current record count and the already-chosen expansion action.
Never creates a dataset version -- Dataset Studio remains the only
place a version is actually written.
"""

from __future__ import annotations

from typing import Any

GROWTH_PERCENT_BY_ACTION: dict[str, float] = {
    "extend": 15.0, "merge": 25.0, "create_new": 40.0, "split": -30.0, "replace": 0.0, "archive": 0.0,
}
RISK_BY_ACTION: dict[str, str] = {
    "extend": "Low", "merge": "Medium", "create_new": "Medium", "split": "Medium", "replace": "High", "archive": "Low",
}


def plan_version(*, current_record_count: int, expansion_action: str) -> dict[str, Any]:
    growth_percent = GROWTH_PERCENT_BY_ACTION.get(expansion_action, 0.0)
    predicted_record_count = max(0, round(current_record_count * (1 + growth_percent / 100)))
    risk = RISK_BY_ACTION.get(expansion_action, "Medium")

    migration_notes = ["schema is unchanged -- MB-11 never modifies Dataset Studio's schema"]
    if expansion_action == "replace":
        migration_notes.append("a replace discards the prior version's record set entirely -- keep the old version for rollback")
    elif expansion_action == "split":
        migration_notes.append("a split produces two or more dataset sources -- downstream training/RAG references must be repointed manually")
    elif expansion_action == "merge":
        migration_notes.append("a merge combines two or more sources -- verify for cross-source duplicate/conflict before committing")
    elif expansion_action == "create_new":
        migration_notes.append("a new dataset source has no prior version history -- treat as v1")

    return {
        "current_record_count": current_record_count,
        "predicted_record_count": predicted_record_count,
        "growth_percent": growth_percent,
        "compatibility": "backward_compatible",
        "risk": risk,
        "migration_notes": migration_notes,
    }
