"""Phase 15 Step 13: model release approval -- separate from, and in
addition to, `ModelReleaseService`'s own role-based approval
(`submit_approval`). Neither one substitutes for the other: the
existing role policy still gates `ModelReleaseService.create_release()`
itself, and this approval additionally gates Phase 15's own
canary/activation steps. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

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
                event_type=f"production_model_release_approval_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_model_release_approval",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_model_release_approval_audit_write_failed", extra={"action": action}
        )


class ProductionModelReleaseApprovalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def request_approval(self, release_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        request = self.repository.get_model_release_request(release_request_public_id)
        if request["status"] != "validated":
            raise ValidationError("only a validated release request may request approval")
        fingerprint = hashlib.sha256(
            dumps_json(
                {
                    "model_candidate": request["model_candidate_public_id"],
                    "release_candidate": request["model_release_candidate_public_id"],
                    "target_assignment_keys": sorted(request["target_assignment_keys"]),
                }
            ).encode()
        ).hexdigest()
        approval = self.repository.create_model_release_approval(
            release_request_public_id,
            {
                "target_assignment_keys": request["target_assignment_keys"],
                "target_fingerprint": fingerprint,
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
        approval = self.repository.approve_model_release_approval(
            approval_public_id, approved_by_admin_id=admin_id, expires_at=expires_at
        )
        self.repository.update_model_release_request(
            approval["release_request_public_id"], {"status": "approved"}
        )
        _audit(
            self._audit, action="approve", actor_reference=admin_id,
            resource_public_id=approval_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def reject(self, release_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        updated = self.repository.update_model_release_request(
            release_request_public_id, {"status": "rejected"}
        )
        _audit(
            self._audit, action="reject", actor_reference=admin_id,
            resource_public_id=release_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated


__all__ = ["ProductionModelReleaseApprovalService"]
