"""MB-12: Pipeline State Machine -- pure. Defines the task's own
twelve named lifecycle states, in order, and the small set of
alternate-path transitions this coordinator allows without treating
them as "skipping a stage": `provider_consensus_pending` only applies
to MB-10's Multi-Provider Consensus mode, so a pipeline in MB-10's
Local Draft mode legitimately reaches `draft_ready` straight from
`under_research`, skipping it. A failed RAG gate is a real backward
move, handled the same way (`dataset_planned` reachable again from
`rag_testing`). Never advances a stage itself --
`dependency_coordinator.py` decides whether a requested transition is
legal.
"""

from __future__ import annotations

STAGE_ORDER = (
    "new", "under_research", "provider_consensus_pending", "draft_ready", "dataset_planned",
    "rag_testing", "training_candidate", "training_running", "benchmark_ready",
    "release_candidate", "completed", "archived",
)

# Maps a target stage to extra source stages it may legally be reached
# from, beyond the one-step-forward default -- either an alternate path
# (skipping a stage that doesn't apply to this session's real MB-10
# mode) or a genuine corrective backward move (a failed RAG gate).
ALLOWED_ALTERNATE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft_ready": ("under_research",),
    "dataset_planned": ("rag_testing",),
}


def stage_index(stage: str) -> int:
    return STAGE_ORDER.index(stage)


def is_one_step_forward(*, current_stage: str, target_stage: str) -> bool:
    return stage_index(target_stage) == stage_index(current_stage) + 1


def is_allowed_alternate_transition(*, current_stage: str, target_stage: str) -> bool:
    return current_stage in ALLOWED_ALTERNATE_TRANSITIONS.get(target_stage, ())
