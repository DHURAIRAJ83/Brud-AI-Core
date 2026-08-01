"""Phase 19 Step 22 -- human review decisions.

Every decision is append-only (`knowledge_gap_reviews`) and attributed.
`decision` drives a governed status/stage transition on the mutable
`knowledge_gap_cases` row -- the review row itself is never mutated.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from core_model.knowledge_gap import REVIEW_DECISIONS

_TRANSITIONS: dict[str, tuple[str, str]] = {
    "confirm_gap": ("review_required", "research"),
    "reclassify": ("classified", "classification"),
    "keep_separate": ("classified", "classification"),
    "needs_evidence": ("evidence_search", "research"),
    "send_to_rag_research": ("rag_trial", "rag_handoff"),
    "send_to_evaluation": ("monitored", "monitoring"),
    "mark_training_assessment_candidate": ("training_assessment_candidate", "training_handoff"),
    "reject": ("rejected", "resolution"),
    "block": ("blocked", "resolution"),
    "archive": ("archived", "retention"),
}


class KnowledgeGapReviewService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)

    def review(
        self,
        case_public_id: str,
        *,
        decision: str,
        comment: str | None,
        reviewed_by_admin_public_id: str,
    ) -> dict[str, object]:
        if decision not in REVIEW_DECISIONS:
            raise ValidationError(f"unknown review decision: {decision!r}")

        case = self.repository.get_case(case_public_id)
        stale_check_fingerprint = f"{case['status']}:{case['stage']}:{case['updated_at']}"

        self.repository.record_review(
            {
                "case_public_id": case_public_id,
                "decision": decision,
                "comment": comment,
                "reviewed_by_admin_public_id": reviewed_by_admin_public_id,
                "stale_check_fingerprint": stale_check_fingerprint,
            }
        )

        transition = _TRANSITIONS.get(decision)
        if transition is not None:
            status, stage = transition
            return self.repository.update_case_status_stage(
                case_public_id, status=status, stage=stage,
                reason=f"review_decision:{decision}", changed_by=reviewed_by_admin_public_id,
            )
        # "merge" and "resolve" are handled by KnowledgeGapMergeService /
        # KnowledgeGapResolutionService respectively -- this review row
        # is still recorded, but the status transition is theirs.
        return self.repository.get_case(case_public_id)


__all__ = ["KnowledgeGapReviewService"]
