"""MB-12: Knowledge Pipeline Manager -- pure. Tracks which of the
task's own eight named lifecycle steps (Public Chat, Knowledge Gap,
Research, Provider Consensus, Dataset Evolution, RAG Validation,
Training Candidate, Release Candidate) already have real evidence,
from already-fetched signals the service gathers by reading MB-08,
MB-09, MB-10, MB-11, and MB-06's own public methods. Never re-derives
any of those signals itself.
"""

from __future__ import annotations

from typing import Any

LIFECYCLE_STEPS = (
    "public_chat", "knowledge_gap", "research", "provider_consensus", "dataset_evolution",
    "rag_validation", "training_candidate", "release_candidate",
)


def track_pipeline(
    *,
    public_chat_activity: bool,
    knowledge_gap_flagged: bool,
    mb09_linked: bool,
    mb10_consensus_done: bool,
    mb11_linked: bool,
    rag_validated: bool,
    mb06_linked: bool,
    release_candidate_present: bool,
) -> dict[str, Any]:
    checklist = {
        "public_chat": public_chat_activity,
        "knowledge_gap": knowledge_gap_flagged,
        "research": mb09_linked,
        "provider_consensus": mb10_consensus_done,
        "dataset_evolution": mb11_linked,
        "rag_validation": rag_validated,
        "training_candidate": mb06_linked,
        "release_candidate": release_candidate_present,
    }
    completed = [step for step in LIFECYCLE_STEPS if checklist[step]]
    completion_percent = round(len(completed) / len(LIFECYCLE_STEPS) * 100, 1)

    return {
        "checklist": checklist,
        "completed_steps": completed,
        "remaining_steps": [step for step in LIFECYCLE_STEPS if not checklist[step]],
        "completion_percent": completion_percent,
    }
