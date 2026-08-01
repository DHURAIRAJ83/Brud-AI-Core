"""Phase 19 Step 18 -- resolution types. Descriptive only: recording a
`resolution_type` never performs the action it describes (never
creates a RAG source, never starts training, never activates a
release) -- it only records what a human decided *should* happen next
and moves the case to a terminal-ish status.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from core_model.knowledge_gap import RESOLUTION_TYPES

_TERMINAL_STATUS = {
    "rejected": "rejected",
    "blocked": "blocked",
    "duplicate_resolved": "resolved",
    "not_reproducible": "resolved",
}


class KnowledgeGapResolutionService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)

    def resolve(
        self,
        case_public_id: str,
        *,
        resolution_type: str,
        notes: str | None,
        resolved_by_admin_public_id: str,
    ) -> dict[str, object]:
        if resolution_type not in RESOLUTION_TYPES:
            raise ValidationError(f"unknown resolution_type: {resolution_type!r}")

        self.repository.record_resolution(
            {
                "case_public_id": case_public_id,
                "resolution_type": resolution_type,
                "notes": notes,
                "resolved_by_admin_public_id": resolved_by_admin_public_id,
            }
        )
        status = _TERMINAL_STATUS.get(resolution_type, "resolved")
        return self.repository.update_case_status_stage(
            case_public_id, status=status, stage="resolution",
            reason=f"resolution:{resolution_type}", changed_by=resolved_by_admin_public_id,
        )

    def list_resolutions(self, case_public_id: str) -> list[dict[str, object]]:
        return self.repository.list_resolutions_for_case(case_public_id)


__all__ = ["KnowledgeGapResolutionService"]
