"""Phase 15 Step 4: production RAG promotion request.

Only ever created once `ProductionRagEligibilityService.check_eligibility()`
passes -- eligibility failure raises before any row is written. Never
writes production state itself; `status` only ever reaches
`ready_for_activation` after a separate approval (Step 7) and a
separate, successfully-validated candidate build (Steps 5-6). See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.production_rag_eligibility_service import ProductionRagEligibilityService
from core_model.production_readiness import COMMERCIAL_USE_CONTEXTS

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_rag_promotion_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_rag_promotion_request",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("production_rag_promotion_audit_write_failed", extra={"action": action})


class ProductionRagPromotionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._eligibility = ProductionRagEligibilityService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_request(self, values: dict[str, Any], *, admin_id: str) -> dict[str, Any]:
        commercial_use_context = values.get("commercial_use_context", "unknown")
        if commercial_use_context not in COMMERCIAL_USE_CONTEXTS:
            raise ValidationError(f"unknown commercial_use_context: {commercial_use_context!r}")

        eligibility = self._eligibility.check_eligibility(
            values["rag_sandbox_experiment_public_id"],
            commercial_use_context=commercial_use_context,
        )
        if not eligibility["eligible"]:
            raise ValidationError(
                "production RAG eligibility failed: " + "; ".join(eligibility["blocking_reasons"])
            )

        fingerprint = hashlib.sha256(
            dumps_json(
                {
                    "checksum": eligibility["accepted_record_checksum_set_hash"],
                    "report_checksum": eligibility["report_checksum_sha256"],
                    "records": sorted(values.get("selected_record_ids", [])),
                }
            ).encode()
        ).hexdigest()

        request = self.repository.create_rag_promotion_request(
            {
                "promotion_code": f"PRP-{uuid4().hex[:16]}",
                "rag_sandbox_experiment_public_id": values["rag_sandbox_experiment_public_id"],
                "rag_sandbox_report_public_id": eligibility["report_public_id"],
                "knowledge_space_public_id": values["knowledge_space_public_id"],
                "selected_record_ids": values.get("selected_record_ids", []),
                "selected_record_checksum_set_hash": eligibility[
                    "accepted_record_checksum_set_hash"
                ],
                "chunking_configuration": values.get("chunking_configuration", {}),
                "embedding_assignment_key": values.get("embedding_assignment_key"),
                "retrieval_configuration": values.get("retrieval_configuration", {}),
                "generation_assignment_key": values.get("generation_assignment_key"),
                "citation_policy_version": values.get("citation_policy_version", "v1"),
                "grounding_policy_version": values.get("grounding_policy_version", "v1"),
                "injection_policy_version": values.get("injection_policy_version", "v1"),
                "commercial_use_context": commercial_use_context,
                "resource_preview": values.get("resource_preview", {}),
                "target_fingerprint": fingerprint,
                "requested_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="create_request", actor_reference=admin_id,
            resource_public_id=request["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"warnings": eligibility["warnings"]},
        )
        return request

    def submit_for_review(self, promotion_public_id: str, *, admin_id: str) -> dict[str, Any]:
        current = self.repository.get_rag_promotion_request(promotion_public_id)
        if current["status"] != "draft":
            raise ValidationError("only a draft promotion request can be submitted for review")
        updated = self.repository.update_rag_promotion_request(
            promotion_public_id, {"status": "awaiting_review"}
        )
        _audit(
            self._audit, action="submit_for_review", actor_reference=admin_id,
            resource_public_id=promotion_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def request_approval(self, promotion_public_id: str, *, admin_id: str) -> dict[str, Any]:
        request = self.repository.get_rag_promotion_request(promotion_public_id)
        if request["status"] not in ("draft", "awaiting_review"):
            raise ValidationError(
                "an approval can only be requested for a draft or awaiting-review request"
            )
        approval = self.repository.create_rag_promotion_approval(
            promotion_public_id,
            {
                "target_fingerprint": request["target_fingerprint"],
                "requested_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="request_approval", actor_reference=admin_id,
            resource_public_id=approval["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def approve(
        self, approval_public_id: str, *, admin_id: str, expires_at: str | None = None
    ) -> dict[str, Any]:
        approval = self.repository.approve_rag_promotion_approval(
            approval_public_id, approved_by_admin_id=admin_id, expires_at=expires_at
        )
        self.repository.update_rag_promotion_request(
            approval["promotion_request_public_id"], {"status": "approved"}
        )
        _audit(
            self._audit, action="approve", actor_reference=admin_id,
            resource_public_id=approval_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return approval


__all__ = ["ProductionRagPromotionService"]
