"""Phase 19 Step 17 -- append-only Admin research notes.

Reuses `detect_secrets()`/`detect_pii()` (via `KnowledgeGapPrivacyService`)
to scan every note before persistence -- a note containing a genuine
secret is rejected outright rather than stored redacted-and-kept,
matching the same policy the capture pipeline already applies to
public questions.
"""

from __future__ import annotations

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.services.knowledge_gap_privacy_service import KnowledgeGapPrivacyService
from core_model.knowledge_gap import RESEARCH_NOTE_TYPES

MAX_NOTE_LENGTH = 4000


class KnowledgeGapResearchService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)
        self.privacy = KnowledgeGapPrivacyService()

    def add_note(
        self,
        case_public_id: str,
        *,
        note_type: str,
        note_text: str,
        source_reference: str | None,
        author_admin_id: str,
    ) -> dict[str, object]:
        if note_type not in RESEARCH_NOTE_TYPES:
            raise ValidationError(f"unknown note_type: {note_type!r}")
        note_text = note_text.strip()
        if not note_text:
            raise ValidationError("note_text must not be empty")
        if len(note_text) > MAX_NOTE_LENGTH:
            raise ValidationError(f"note_text exceeds max length of {MAX_NOTE_LENGTH}")

        privacy_result = self.privacy.process(note_text)
        if privacy_result.content_unavailable_for_review:
            raise ValidationError(
                "this note appears to contain a credential or secret and cannot be stored -- "
                "remove it and try again"
            )

        return self.repository.record_research_note(
            {
                "case_public_id": case_public_id,
                "note_type": note_type,
                "note_text_redacted": privacy_result.redacted_question,
                "source_reference": source_reference,
                "author_admin_id": author_admin_id,
            }
        )

    def list_notes(self, case_public_id: str) -> list[dict[str, object]]:
        return self.repository.list_notes_for_case(case_public_id)


__all__ = ["MAX_NOTE_LENGTH", "KnowledgeGapResearchService"]
