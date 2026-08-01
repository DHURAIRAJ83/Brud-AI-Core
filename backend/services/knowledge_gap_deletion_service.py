"""Phase 19 Step 24 -- privacy-governed deletion and forgetting.

Deletion never removes the case row or its append-only audit trail
(occurrences, reviews, status events, resolution events) -- it only
clears the redacted/canonical question payload and flips
`content_unavailable_for_review`/`status='deleted_payload'`, so a
`knowledge_gap_cases` row always remains as minimal, non-personal
evidence that a case existed and was resolved this way, honoring the
"deletion must never silently erase safety/security audit
obligations" rule. No scheduler here -- every step is Admin-triggered.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository


class KnowledgeGapDeletionService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)

    def request(
        self, case_public_id: str, *, requested_by_admin_public_id: str, reason: str | None
    ) -> dict[str, object]:
        self.repository.get_case(case_public_id)
        return self.repository.request_deletion(
            {
                "case_public_id": case_public_id,
                "requested_by_admin_public_id": requested_by_admin_public_id,
                "reason": reason,
            }
        )

    def impact_preview(self, case_public_id: str) -> dict[str, object]:
        case = self.repository.get_case(case_public_id)
        occurrences = self.repository.list_occurrences_for_case(case_public_id, limit=100)
        notes = self.repository.list_notes_for_case(case_public_id)
        return {
            "case_public_id": case_public_id,
            "occurrence_count": len(occurrences),
            "research_note_count": len(notes),
            "cluster_public_id": case["cluster_public_id"],
            "will_retain": [
                "case row (status=deleted_payload)", "occurrence audit history",
                "review/resolution/status-event history",
            ],
            "will_remove": ["redacted_question", "canonical_question"],
        }

    def confirm(self, case_public_id: str, *, admin_public_id: str) -> dict[str, object]:
        state = self.repository.latest_deletion_state(case_public_id)
        if state != "requested":
            raise ValidationError(
                f"deletion request for {case_public_id} is not in 'requested' state "
                f"(current: {state!r})"
            )
        return self.repository.advance_deletion_state(
            case_public_id, state="confirmed", admin_public_id=admin_public_id
        )

    def execute(self, case_public_id: str, *, admin_public_id: str) -> dict[str, object]:
        state = self.repository.latest_deletion_state(case_public_id)
        if state != "confirmed":
            raise ValidationError(
                f"deletion request for {case_public_id} is not in 'confirmed' state "
                f"(current: {state!r})"
            )
        case = self.repository.execute_case_deletion(case_public_id)
        self.repository.advance_deletion_state(
            case_public_id, state="executed", admin_public_id=admin_public_id
        )
        return case

    def reject(self, case_public_id: str, *, admin_public_id: str) -> dict[str, object]:
        return self.repository.advance_deletion_state(
            case_public_id, state="rejected", admin_public_id=admin_public_id
        )


__all__ = ["KnowledgeGapDeletionService"]
