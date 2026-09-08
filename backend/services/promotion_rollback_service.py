"""Phase 24 — Atomic Promotion & Non-Destructive Rollback Backend Service.

Executes atomic promotion of active version pointers for RAG knowledge spaces and Dataset exports,
performs post-promotion integrity verification, and executes non-destructive rollback.

CRITICAL INVARIANTS:
- Explicit human admin approval is strictly mandatory before promotion or rollback.
- Promotion is atomic: pointer updates and promotion log creation execute within a transaction.
- Rollback is non-destructive: pointer is updated back to a historical release version without deleting history or files.
- Idempotent promotion: repeated identical promotion requests return existing operation log without creating duplicate entries.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from backend.database.repositories.release_repository import ReleaseRepository
from core_model.capabilities.release_management_service import (
    RELEASE_STAGE_ACTIVE,
    RELEASE_STAGE_APPROVED,
    RELEASE_STAGE_READY_FOR_PROMOTION,
    RELEASE_STAGE_ROLLED_BACK,
    PromotionOperation,
    ReleaseCandidate,
    ReleaseManagementService,
    RollbackOperation,
    compute_promotion_idempotency_key,
)


class PromotionRollbackService:
    """Backend service for executing atomic release promotion and non-destructive rollback."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.release_repo = ReleaseRepository(conn)
        self.domain_service = ReleaseManagementService()

    def promote_release(
        self,
        release_id: str,
        *,
        approved_by: str,
        space_or_target_id: str = "default",
    ) -> tuple[ReleaseCandidate, PromotionOperation]:
        """Atomically promote a RELEASE_APPROVED candidate to ACTIVE production version."""
        candidate = self.release_repo.get_release_by_id(release_id)
        if not candidate:
            raise ValueError(f"Release candidate '{release_id}' not found.")

        # Idempotency Check
        idemp_key = compute_promotion_idempotency_key(candidate.release_id, candidate.release_version)
        existing_op = self.release_repo.get_promotion_by_idempotency_key(idemp_key)
        if existing_op and candidate.release_status == RELEASE_STAGE_ACTIVE:
            return candidate, existing_op

        # Fetch current active version pointer for space
        current_pointer = self.release_repo.get_active_version_pointer(
            candidate.artifact_type, space_or_target_id
        )
        prev_version = current_pointer["active_release_version"] if current_pointer else None

        active_candidate, promotion_op = self.domain_service.promote_release(
            candidate, previous_active_version=prev_version, approved_by=approved_by
        )

        now_str = datetime.now(UTC).isoformat()

        # Atomic database transaction
        with self.conn:
            self.release_repo.update_release_status(active_candidate)
            self.release_repo.insert_promotion_operation(promotion_op)
            self.release_repo.update_active_version_pointer(
                artifact_type=active_candidate.artifact_type,
                space_or_target_id=space_or_target_id,
                active_release_id=active_candidate.release_id,
                active_release_version=active_candidate.release_version,
                updated_by=approved_by,
                updated_at=now_str,
            )

        return active_candidate, promotion_op

    def rollback_release(
        self,
        release_id: str,
        target_historical_version: str,
        *,
        approved_by: str,
        reason: str = "Administrative rollback",
        space_or_target_id: str = "default",
    ) -> tuple[ReleaseCandidate, RollbackOperation]:
        """Execute non-destructive rollback from active release version to historical target release version."""
        candidate = self.release_repo.get_release_by_id(release_id)
        if not candidate:
            raise ValueError(f"Release candidate '{release_id}' not found.")

        rolled_back_candidate, rollback_op = self.domain_service.rollback_release(
            candidate, target_historical_version, approved_by=approved_by, reason=reason
        )

        now_str = datetime.now(UTC).isoformat()

        # Atomic transaction updating status and pointer without deleting history
        with self.conn:
            self.release_repo.update_release_status(rolled_back_candidate)
            self.release_repo.insert_rollback_operation(rollback_op)
            self.release_repo.update_active_version_pointer(
                artifact_type=rolled_back_candidate.artifact_type,
                space_or_target_id=space_or_target_id,
                active_release_id=f"rel-rb-{target_historical_version}",
                active_release_version=target_historical_version,
                updated_by=approved_by,
                updated_at=now_str,
            )

        return rolled_back_candidate, rollback_op
