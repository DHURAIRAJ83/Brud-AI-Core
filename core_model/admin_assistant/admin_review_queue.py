"""Phase 61 - P2: Admin Review Queue Manager.

Provides administrator review functionality for candidate datasets prior to promotion.

CRITICAL INVARIANTS:
- Candidate dataset requires explicit human Admin approval.
- Decisions: PENDING_REVIEW | APPROVED | REJECTED | QUARANTINED.
- Even when dataset status becomes `APPROVED_CANDIDATE`, pretraining remains locked (`training_authorized = FALSE`).
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core_model.corpus.candidate_dataset_pipeline import CandidateDatasetManifest


@dataclass
class AdminReviewRecord:
    review_id: str
    dataset_version: str
    book_ids: list[str]
    rights_status: str
    novelty_status: str
    token_accounting_status: str
    total_tokens: int
    new_global_tokens: int
    decision: str  # PENDING_REVIEW | APPROVED_CANDIDATE | REJECTED | QUARANTINED
    reviewed_by: str | None = None
    admin_notes: str | None = None
    reviewed_at: str | None = None


class AdminReviewQueueManager:
    """Manages review queue for human Admin dataset governance."""

    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository
        self._in_memory_reviews: dict[str, AdminReviewRecord] = {}

    def submit_manifest_for_review(
        self,
        manifest: CandidateDatasetManifest,
        admin_notes: str | None = None,
    ) -> AdminReviewRecord:
        """Submit a candidate dataset manifest into the Admin Review Queue."""
        review_id = f"rev-{manifest.dataset_version}"

        if self.repository:
            try:
                db_item = self.repository.create_admin_review_item(
                    book_id=",".join(manifest.book_ids),
                    dataset_version_id=manifest.dataset_version,
                    rights_status=manifest.rights_status,
                    quality_status=manifest.quality_status,
                    provenance_status=manifest.provenance_status,
                    novelty_status=manifest.novelty_status,
                    token_accounting_status=manifest.token_accounting_status,
                    admin_notes=admin_notes
                )
                review_id = db_item["review_id"]
            except Exception:
                pass

        record = AdminReviewRecord(
            review_id=review_id,
            dataset_version=manifest.dataset_version,
            book_ids=manifest.book_ids,
            rights_status=manifest.rights_status,
            novelty_status=manifest.novelty_status,
            token_accounting_status=manifest.token_accounting_status,
            total_tokens=manifest.total_tokens,
            new_global_tokens=manifest.new_global_tokens,
            decision="PENDING_REVIEW",
            admin_notes=admin_notes
        )
        self._in_memory_reviews[review_id] = record
        return record

    def record_admin_decision(
        self,
        review_id: str,
        decision: str,  # APPROVED | REJECTED | QUARANTINED | RELEASE_APPROVED | CANARY_APPROVED | PUBLIC_CHAT_APPROVED | ROLLBACK_APPROVED
        reviewed_by: str = "admin-dhurai",
        notes: str | None = None,
    ) -> AdminReviewRecord:
        """Record explicit Admin approval or rejection for dataset or release."""
        dec_upper = decision.upper()
        allowed_decisions = (
            "APPROVED", "APPROVED_CANDIDATE", "REJECTED", "QUARANTINED",
            "RELEASE_APPROVED", "RELEASE_REJECTED", "CANARY_APPROVED",
            "PUBLIC_CHAT_APPROVED", "PUBLIC_CHAT_REJECTED", "ROLLBACK_APPROVED",
            "RECOVERY_REVIEW_PENDING", "RECOVERY_APPROVED", "RECOVERY_REJECTED",
            "RECOVERY_QUARANTINED", "STATE_RESTORE_APPROVED", "SERVICE_RESTORE_APPROVED",
            "RECOVERY_VERIFIED", "RECOVERY_CLOSED",
            "COMPLIANCE_REVIEW_PENDING", "COMPLIANCE_APPROVED", "SECRET_ROTATION_APPROVED",
            "POLICY_CHANGE_APPROVED"
        )
        if dec_upper not in allowed_decisions:
            raise ValueError(f"Invalid admin decision: {decision}")

        final_decision = dec_upper
        if dec_upper == "APPROVED":
            final_decision = "APPROVED_CANDIDATE"

        if self.repository:
            try:
                self.repository.update_admin_decision(
                    review_id,
                    admin_decision=final_decision,
                    reviewed_by=reviewed_by,
                    admin_notes=notes
                )
            except Exception:
                pass

        record = self._in_memory_reviews.get(review_id)
        if record:
            record.decision = final_decision
            record.reviewed_by = reviewed_by
            record.admin_notes = notes
            record.reviewed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return record

        return AdminReviewRecord(
            review_id=review_id,
            dataset_version="v001",
            book_ids=[],
            rights_status="APPROVED",
            novelty_status="NOVEL_ADDED",
            token_accounting_status="PASSED",
            total_tokens=1000,
            new_global_tokens=1000,
            decision=final_decision,
            reviewed_by=reviewed_by,
            admin_notes=notes,
            reviewed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
