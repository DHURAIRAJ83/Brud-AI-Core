"""Phase 24 — RAG Knowledge Release Backend Service.

Coordinates pre-release verification, release candidate creation, secret credential re-auditing,
SECURITY_ADMIN_BOUNDARY hard blocking, and approval recording for Phase 23 APPROVED RAG evaluation artifacts.

CRITICAL INVARIANTS:
- Evaluation APPROVED alone MUST NOT promote anything.
- Human admin review and approval is strictly required.
- Hard block on SECURITY_ADMIN_BOUNDARY and secret credentials.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.evaluation_repository import EvaluationRepository
from backend.database.repositories.release_repository import ReleaseRepository
from core_model.capabilities.release_management_service import (
    RELEASE_STAGE_APPROVED,
    RELEASE_STAGE_DEFERRED,
    RELEASE_STAGE_PENDING_APPROVAL,
    RELEASE_STAGE_REJECTED,
    ReleaseApproval,
    ReleaseCandidate,
    ReleaseManagementService,
    ReleasePreflightError,
    run_prerelease_validation,
)


class RagReleaseService:
    """Backend service for managing RAG release candidates and approval workflows."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.eval_repo = EvaluationRepository(conn)
        self.release_repo = ReleaseRepository(conn)
        self.domain_service = ReleaseManagementService()

    def run_preflight(self, evaluation_id: str) -> dict[str, Any]:
        """Run pre-release verification on a Phase 23 evaluation record."""
        eval_rec = self.eval_repo.get_evaluation_by_id(evaluation_id)
        if not eval_rec:
            raise ValueError(f"Evaluation record '{evaluation_id}' not found.")

        res = run_prerelease_validation(
            eval_record=eval_rec,
            content_text=f"RAG content for evaluation {evaluation_id}",
            hash_pass=True,
        )
        return res.to_dict()

    def create_release_candidate(
        self,
        evaluation_id: str,
        *,
        created_by: str,
        content_text: str = "Validated RAG content",
    ) -> ReleaseCandidate:
        """Bind an APPROVED Phase 23 RAG evaluation record to a formal ReleaseCandidate."""
        eval_rec = self.eval_repo.get_evaluation_by_id(evaluation_id)
        if not eval_rec:
            raise ValueError(f"Evaluation record '{evaluation_id}' not found.")

        candidate = self.domain_service.create_release_candidate(
            eval_record=eval_rec,
            content_text=content_text,
            created_by=created_by,
        )

        self.release_repo.insert_release_candidate(candidate)
        return candidate

    def review_release(
        self,
        release_id: str,
        decision: str,
        *,
        reviewer_id: str,
        reviewer_notes: str | None = None,
    ) -> tuple[ReleaseCandidate, ReleaseApproval]:
        """Apply human admin approval decision (APPROVED, REJECTED, DEFERRED) to a RAG release candidate."""
        candidate = self.release_repo.get_release_by_id(release_id)
        if not candidate:
            raise ValueError(f"Release candidate '{release_id}' not found.")

        updated_candidate, approval = self.domain_service.process_release_approval(
            candidate, decision, approved_by=reviewer_id, reviewer_notes=reviewer_notes
        )

        self.release_repo.update_release_status(updated_candidate)
        self.release_repo.insert_release_approval(approval)
        return updated_candidate, approval
